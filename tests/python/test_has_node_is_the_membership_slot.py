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


MEMBERSHIP_FORMS = ["contains", "has_node", "raw_has_node"]


def _membership_call(lib, cls_name, graph, key, form):
    if form == "contains":
        return key in graph
    if form == "raw_has_node" and lib is fnx:
        return fnx._RAW_HAS_NODE_METHODS[CLASSES.index(cls_name)](graph, key)
    return graph.has_node(n=key)


def _membership_outcome(lib, cls_name, graph, key, form):
    try:
        return _membership_call(lib, cls_name, graph, key, form)
    except Exception as exc:  # noqa: BLE001 - callback errors are observable
        return "raised", type(exc).__name__, str(exc)


def _hash_reentry_probe(lib, cls_name, form, key_kind, action):
    graph = getattr(lib, cls_name)()
    graph.add_node("anchor")
    armed = False
    changed = False
    trace = []

    def query_hash(key, value):
        nonlocal changed
        if armed and key is query:
            trace.append("hash")
            if not changed:
                changed = True
                if action == "add":
                    graph.add_node(stored)
                elif action == "remove":
                    graph.remove_node(stored)
                else:
                    graph.clear()
                trace.append(action)
        return value

    if key_kind == "int":
        class Node(int):
            def __hash__(self):
                return query_hash(self, int.__hash__(self))

        stored, query = 41, Node(41)
    elif key_kind == "str":
        class Node(str):
            def __hash__(self):
                return query_hash(self, str.__hash__(self))

        stored, query = "target", Node("target")
    else:
        class Node:
            def __hash__(self):
                return query_hash(self, 671023)

            def __eq__(self, other):
                return isinstance(other, Node)

        stored, query = Node(), Node()

    if action != "add":
        graph.add_node(stored)
    armed = True
    outcome = _membership_outcome(lib, cls_name, graph, query, form)
    armed = False
    return outcome, trace, len(graph), stored in graph, "anchor" in graph


@pytest.mark.parametrize("cls_name", CLASSES)
@pytest.mark.parametrize("form", MEMBERSHIP_FORMS)
@pytest.mark.parametrize("key_kind", ["int", "str", "object"])
@pytest.mark.parametrize("action", ["add", "remove", "clear"])
def test_membership_hash_callback_can_mutate_the_graph(
    cls_name, form, key_kind, action
):
    """Hash once, release the native borrow, and look up the updated topology."""
    expected = _hash_reentry_probe(nx, cls_name, form, key_kind, action)
    assert expected[0] is (action == "add")
    assert expected[1] == ["hash", action]
    assert _hash_reentry_probe(fnx, cls_name, form, key_kind, action) == expected


def _hash_error_probe(lib, cls_name, form, error_type):
    graph = getattr(lib, cls_name)()
    calls = []

    class Node:
        def __hash__(self):
            calls.append("hash")
            graph.add_node("callback-node")
            raise error_type("membership callback failed")

    outcome = _membership_outcome(lib, cls_name, graph, Node(), form)
    return outcome, calls, list(graph)


@pytest.mark.parametrize("cls_name", CLASSES)
@pytest.mark.parametrize("form", MEMBERSHIP_FORMS)
@pytest.mark.parametrize("error_type", [TypeError, ValueError, RuntimeError])
def test_membership_hash_errors_are_not_retried_or_silenced(
    cls_name, form, error_type
):
    expected = _hash_error_probe(nx, cls_name, form, error_type)
    assert expected[1:] == (["hash"], ["callback-node"])
    if error_type is TypeError:
        assert expected[0] is False
    else:
        assert expected[0] == (
            "raised", error_type.__name__, "membership callback failed"
        )
    assert _hash_error_probe(fnx, cls_name, form, error_type) == expected


def _equality_reentry_probe(lib, cls_name, form, action):
    graph = getattr(lib, cls_name)()
    armed = False
    changed = False
    trace = []

    class Node:
        def __hash__(self):
            if armed and self is query:
                trace.append("hash")
            return 671029

        def __eq__(self, other):
            nonlocal changed
            if not isinstance(other, Node):
                return False
            if armed and self is stored and not changed:
                changed = True
                trace.append("equality")
                if action == "remove":
                    graph.remove_node(stored)
                elif action == "clear":
                    graph.clear()
                elif action == "type_error":
                    raise TypeError("equality callback failed")
                elif action == "value_error":
                    raise ValueError("equality callback failed")
                else:
                    graph.add_edge("left", "right")
            return True

    stored, query = Node(), Node()
    graph.add_node(stored)
    armed = True
    outcome = _membership_outcome(lib, cls_name, graph, query, form)
    armed = False
    return outcome, trace, len(graph), stored in graph


@pytest.mark.parametrize("cls_name", CLASSES)
@pytest.mark.parametrize("form", MEMBERSHIP_FORMS)
@pytest.mark.parametrize(
    "action", ["remove", "clear", "add_edge", "type_error", "value_error"]
)
def test_membership_equal_alias_callbacks_observe_reference_boundaries(
    cls_name, form, action
):
    expected = _equality_reentry_probe(nx, cls_name, form, action)
    assert expected[1] == ["hash", "equality"]
    assert _equality_reentry_probe(fnx, cls_name, form, action) == expected
