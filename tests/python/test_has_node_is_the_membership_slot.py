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
