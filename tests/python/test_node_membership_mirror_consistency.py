"""Node membership must not depend on whether the iteration mirror is built.

br-r37-c1-770z8. `exact_str_node_is_present` (which backs BOTH `G.has_node(s)`
and `s in G`) answers from the node-iteration mirror when that mirror is already
materialized, because a `PyDict` lookup reuses CPython's cached str hash instead
of rebuilding and re-hashing the `"str:{len}:{s}"` canonical key.

That makes membership depend on an internal cache's existence, so the invariant
worth pinning is exactly that it must NOT: every probe has to give the same
answer whether or not something has iterated the nodes first, and both must
agree with networkx.

The negative case a wrong implementation fails is a mutation performed AFTER the
mirror is materialized. An implementation that reads a stale mirror passes every
freshly-built-graph test and fails here.
"""

import random

import networkx as nx
import pytest

import franken_networkx as fnx

CLASSES = ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"]
PROBES = ["a", "b", "c", "zz", "n0", "n3", "", "A", "0"]


def _pair(class_name):
    return getattr(fnx, class_name)(), getattr(nx, class_name)()


def _membership(graph):
    """Both spellings — they share one helper and must never disagree."""
    return [(p, p in graph, graph.has_node(p)) for p in PROBES]


@pytest.mark.parametrize("class_name", CLASSES)
def test_membership_identical_with_and_without_materialized_mirror(class_name):
    cold, reference = _pair(class_name)
    warm, _ = _pair(class_name)
    for graph in (cold, warm, reference):
        graph.add_edge("a", "b")
        graph.add_node("c")
    list(warm)  # materialize the iteration mirror on this one only

    expected = [(p, p in reference, reference.has_node(p)) for p in PROBES]
    assert _membership(cold) == expected, "cold (no mirror) diverges from networkx"
    assert _membership(warm) == expected, "warm (mirror built) diverges from networkx"


@pytest.mark.parametrize("class_name", CLASSES)
def test_mutations_after_materialization_are_visible_to_membership(class_name):
    """The negative case: a stale mirror passes every fresh-graph test."""
    graph, reference = _pair(class_name)
    for target in (graph, reference):
        target.add_edge("a", "b")
    list(graph)  # materialize BEFORE mutating

    for target in (graph, reference):
        target.add_node("c")
        target.remove_node("a")
        target.add_edge("d", "e")
        target.add_nodes_from(["f", "g"])
        target.remove_nodes_from(["f"])

    expected = [(p, p in reference, reference.has_node(p)) for p in PROBES + ["d", "f", "g"]]
    actual = [(p, p in graph, graph.has_node(p)) for p in PROBES + ["d", "f", "g"]]
    assert actual == expected, (
        "membership went stale after mutations that followed mirror "
        f"materialization: fnx {actual} vs networkx {expected}"
    )


@pytest.mark.parametrize("class_name", CLASSES)
def test_clear_is_visible_to_membership(class_name):
    graph, reference = _pair(class_name)
    for target in (graph, reference):
        target.add_edge("a", "b")
    list(graph)
    for target in (graph, reference):
        target.clear()
    assert _membership(graph) == [
        (p, p in reference, reference.has_node(p)) for p in PROBES
    ]


@pytest.mark.parametrize("class_name", CLASSES)
def test_randomized_mutations_keep_membership_and_iteration_in_agreement(class_name):
    """Fuzz: membership, iteration and networkx must agree at every step.

    Iteration is included because it is what the mirror actually backs — if
    membership and iteration ever disagree, one of them is reading a stale
    structure, and this says which.
    """
    rng = random.Random(770)
    for trial in range(40):
        graph, reference = _pair(class_name)
        for target in (graph, reference):
            target.add_edge("a", "b")
        if trial % 2:
            list(graph)  # half the trials run with the mirror materialized
        for step in range(10):
            operation = rng.randrange(6)
            left, right = f"n{rng.randrange(5)}", f"n{rng.randrange(5)}"
            for target in (graph, reference):
                if operation == 0:
                    target.add_node(left)
                elif operation == 1:
                    target.add_edge(left, right)
                elif operation == 2 and left in target:
                    target.remove_node(left)
                elif operation == 3:
                    target.add_nodes_from([left, right, "zz"])
                elif operation == 4:
                    target.remove_nodes_from([n for n in (left, right) if n in target])
                elif operation == 5:
                    target.add_edges_from([(left, right), (right, "q")])

            assert set(graph) == set(reference), (
                f"iteration drifted at trial={trial} step={step} op={operation}"
            )
            probes = PROBES + [left, right, "q", "zz"]
            assert [(p, p in graph) for p in probes] == [
                (p, p in reference) for p in probes
            ], f"membership drifted at trial={trial} step={step} op={operation}"
            assert [graph.has_node(p) for p in probes] == [
                p in graph for p in probes
            ], "has_node and `in` disagree — they share one helper"


@pytest.mark.parametrize("class_name", CLASSES)
def test_non_string_and_unhashable_keys_still_match_networkx(class_name):
    """The mirror path is entered only for an exact `str`; guard the rest.

    Ints, floats, bools and unhashable keys must keep their existing behaviour
    whether or not the mirror is built — a mirror lookup uses `__eq__`, so an
    int probe must not start matching a string node.
    """
    graph, reference = _pair(class_name)
    warm, _ = _pair(class_name)
    for target in (graph, warm, reference):
        target.add_node("1")
        target.add_node(2)
        target.add_edge("a", "b")
    list(warm)

    for probe in (1, 2, 2.0, True, False, "1", "2", None):
        expected = (probe in reference, reference.has_node(probe))
        assert (probe in graph, graph.has_node(probe)) == expected, (
            f"cold graph diverged on {probe!r}"
        )
        assert (probe in warm, warm.has_node(probe)) == expected, (
            f"warm graph diverged on {probe!r}"
        )

    for unhashable in ([1], {"a": 1}, {1, 2}):
        expected_in = unhashable in reference
        assert (unhashable in graph) == expected_in
        assert (unhashable in warm) == expected_in
