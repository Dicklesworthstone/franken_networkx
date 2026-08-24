"""``G.has_node(n)`` and ``n in G`` must answer identically, on every key shape.

br-r37-c1-hasnode-slot. ``has_node`` is now routed through the membership slot,
because the native method form of the same question cost 1.36-1.72x the slot form
on all four classes (Graph 768.9ns against 447.2ns, networkx 68.4ns). That is
only a safe trade while the two spellings are the SAME question, so this file
asserts it against networkx rather than against a remembered constant.

THE AXES ARE THE ONES THAT ACTUALLY SEPARATE THE TWO PATHS, not a sweep for its
own sake. The native ``has_node`` and the native ``__contains__`` share the
identity-int fast path and the exact-``str`` present memo, then diverge in what
they consult:

  * an UNHASHABLE key is ABSENT in networkx (``try: n in self._node except
    TypeError: return False``) - fnx canonicalises by reading characters and
    never calls ``__hash__``, so a ``str`` subclass with ``__hash__ = None``
    once reported True for a node it can never reach (br-r37-c1-lvlu7);
  * an ASSIGNED private ``_node`` mapping is consulted by ``__contains__`` and
    was NOT read by the native ``has_node`` at all, so a graph carrying one is
    the case where routing through the slot changes which store answers;
  * ints, bools and floats collide in the canonical key space (``True`` and
    ``1``), which is where a fast path that trusts a type check goes wrong.
"""

from __future__ import annotations

import networkx as nx
import pytest

import franken_networkx as fnx

CLASSES = ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"]


class _Unhashable(str):
    """A str that cannot be hashed - absent in networkx, whatever it spells."""

    __hash__ = None


def _pair(cls_name):
    fx, ref = getattr(fnx, cls_name)(), getattr(nx, cls_name)()
    for graph in (fx, ref):
        graph.add_nodes_from([str(i) for i in range(10)])
        graph.add_node(5)
        graph.add_edge("0", "1")
    return fx, ref


def _probe(graph, key):
    """(has_node, in) for one key, exceptions captured by type."""
    out = []
    for call in (lambda: graph.has_node(key), lambda: key in graph):
        try:
            out.append(call())
        except Exception as exc:  # noqa: BLE001 - the type IS the answer here
            out.append(("raised", type(exc).__name__))
    return tuple(out)


KEYS = [
    ("present str", "3"),
    ("absent str", "not-a-node"),
    ("empty str", ""),
    ("present int", 5),
    ("absent int", 987654),
    ("int that spells a present str", 3),
    ("bool True", True),
    ("bool False", False),
    ("float", 1.0),
    ("negative int", -1),
    ("tuple", (1, 2)),
    ("None", None),
]


@pytest.mark.parametrize("cls_name", CLASSES)
@pytest.mark.parametrize("label,key", KEYS, ids=[k[0] for k in KEYS])
def test_both_spellings_agree_with_networkx(cls_name, label, key):
    fx, ref = _pair(cls_name)
    fx_has, fx_in = _probe(fx, key)
    ref_has, ref_in = _probe(ref, key)

    assert fx_has == fx_in, (
        f"{cls_name} {label}: fnx has_node={fx_has!r} but `in`={fx_in!r} - the "
        "two spellings are one question and has_node is routed through the slot"
    )
    assert fx_has == ref_has, f"{cls_name} {label}: fnx {fx_has!r}, nx {ref_has!r}"


@pytest.mark.parametrize("cls_name", CLASSES)
def test_an_unhashable_key_is_absent_in_both_spellings(cls_name):
    """br-r37-c1-lvlu7's contract, asserted for the routed spelling too."""
    fx, ref = _pair(cls_name)
    key = _Unhashable("3")

    assert _probe(fx, key) == _probe(ref, key) == (False, False)


@pytest.mark.parametrize("cls_name", CLASSES)
def test_an_assigned_private_node_store_answers_both_spellings(cls_name):
    """The case where routing through the slot CHANGES which store answers.

    A NetworkX utility can assign ``G._node``; from then on that mapping is the
    truth. ``__contains__`` reads it, the native ``has_node`` did not, and the
    per-instance shadow is what used to reconcile them - so this pins the whole
    arrangement rather than any one half of it.
    """
    fx, ref = _pair(cls_name)
    for graph in (fx, ref):
        graph._node = {"3": {}, "assigned-only": {}}

    for key in ("3", "assigned-only", "7"):
        assert _probe(fx, key) == _probe(ref, key), key


@pytest.mark.parametrize("cls_name", CLASSES)
def test_the_routed_spelling_still_accepts_the_keyword(cls_name):
    """networkx's ``def has_node(self, n)`` accepts ``n=``; so must this.

    br-r37-c1-nbritype pinned the same property for ``neighbors`` after a
    positional-only signature broke it, and making ``has_node`` positional-only
    is exactly the cheap way to shave the trampoline this change avoids taking.
    """
    fx, ref = _pair(cls_name)

    assert fx.has_node(n="3") == ref.has_node(n="3") is True
    assert fx.has_node(n="absent") == ref.has_node(n="absent") is False


@pytest.mark.parametrize("cls_name", CLASSES)
def test_mutation_is_visible_to_both_spellings(cls_name):
    """A memo that outlived a removal would show up here and nowhere else."""
    fx, ref = _pair(cls_name)

    for graph in (fx, ref):
        graph.add_node("fresh")
    assert _probe(fx, "fresh") == _probe(ref, "fresh") == (True, True)

    for graph in (fx, ref):
        graph.remove_node("fresh")
    assert _probe(fx, "fresh") == _probe(ref, "fresh") == (False, False)

    for graph in (fx, ref):
        graph.remove_node("3")
    assert _probe(fx, "3") == _probe(ref, "3") == (False, False)


# ---------------------------------------------------------------------------
# br-r37-c1-hasnode-slot, architectural half: has_node now answers from the LIVE
# node-key mirror without entering Rust at all. That removes the ~210-250ns
# boundary crossing (0.15x -> 0.75x of networkx) and introduces exactly one new
# hazard: a cached handle that stops describing the graph it is attached to.
# Everything below is about that hazard.
# ---------------------------------------------------------------------------

MUTATIONS = [
    ("add_node", lambda g: g.add_node("fresh"), "fresh", True),
    ("add_nodes_from", lambda g: g.add_nodes_from(["fresh", "f2"]), "f2", True),
    ("add_edge creates nodes", lambda g: g.add_edge("fresh", "f3"), "f3", True),
    ("add_edges_from creates nodes", lambda g: g.add_edges_from([("f4", "f5")]), "f4", True),
    ("remove_node", lambda g: g.remove_node("3"), "3", False),
    ("remove_nodes_from", lambda g: g.remove_nodes_from(["3", "4"]), "4", False),
    ("clear", lambda g: g.clear(), "3", False),
]


@pytest.mark.parametrize("cls_name", CLASSES)
@pytest.mark.parametrize(
    "label,mutate,probe,expected", MUTATIONS, ids=[m[0] for m in MUTATIONS]
)
def test_a_warm_mirror_tracks_every_mutation_spelling(
    cls_name, label, mutate, probe, expected
):
    """The cache is a handle to a LIVE dict, so mutations need no invalidation.

    That is the whole basis of the design, so it is asserted per spelling rather
    than once: a spelling that rebuilt the mirror object instead of updating it
    would leave `has_node` answering from a detached dict, which is a wrong
    answer and not a slow one.
    """
    fx, ref = _pair(cls_name)
    assert fx.has_node("3") is ref.has_node("3") is True  # warm the mirror first

    mutate(fx)
    mutate(ref)

    assert fx.has_node(probe) is ref.has_node(probe) is expected


@pytest.mark.parametrize("cls_name", CLASSES)
def test_the_cached_handle_is_the_graphs_own_live_mirror(cls_name):
    """Identity, not equality: a copy of the dict would go stale silently."""
    fx, _ = _pair(cls_name)
    fx.has_node("3")

    assert fx._fnx_has_node_key_mirror is fx._fnx_node_key_dict()


@pytest.mark.parametrize("cls_name", CLASSES)
@pytest.mark.parametrize(
    "label",
    ["copy", "copy.copy", "copy.deepcopy", "pickle", "to_directed", "relabel"],
)
def test_a_copy_never_inherits_the_source_graphs_mirror(cls_name, label):
    """THE dangerous case: a handle to another graph's nodes.

    If the attribute rode along on a copy, the copy would answer membership from
    the SOURCE's node set - true for nodes it does not have, false for nodes it
    does. The `_fnx_` prefix keeps it out of the copy/pickle paths; this asserts
    the outcome rather than the convention.
    """
    import copy as _copy
    import pickle as _pickle

    source, _ = _pair(cls_name)
    source.has_node("3")  # warm, so there IS something that could be inherited

    if label == "copy":
        clone = source.copy()
    elif label == "copy.copy":
        clone = _copy.copy(source)
    elif label == "copy.deepcopy":
        clone = _copy.deepcopy(source)
    elif label == "pickle":
        clone = _pickle.loads(_pickle.dumps(source))
    elif label == "to_directed":
        clone = source.to_directed()
    else:
        clone = fnx.relabel_nodes(source, {"3": "renamed"}, copy=True)

    assert not hasattr(clone, "_fnx_has_node_key_mirror"), (
        f"{label} carried the source graph's node-key handle onto the copy"
    )

    clone.add_node("only-in-the-clone")
    assert clone.has_node("only-in-the-clone") is True
    assert source.has_node("only-in-the-clone") is False


@pytest.mark.parametrize("cls_name", CLASSES)
def test_a_view_does_not_answer_from_the_underlying_mirror(cls_name):
    """br-r37-c1-kum9v: a view subclasses the native class with an EMPTY base.

    The accessor exists on it, so an eligibility test by `isinstance` would take
    the mirror and report every node absent. Type identity is what excludes it,
    and this asserts the answers a view must give.
    """
    fx, ref = _pair(cls_name)
    keep = ["0", "1", "2"]

    fx_view, ref_view = fx.subgraph(keep), ref.subgraph(keep)

    assert fx_view.has_node("0") is ref_view.has_node("0") is True
    assert fx_view.has_node("7") is ref_view.has_node("7") is False
