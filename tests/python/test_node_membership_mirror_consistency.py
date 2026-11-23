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
import sys

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


def _node_iterator(graph, surface):
    if surface == "graph":
        return iter(graph)
    if surface == "nodes":
        return iter(graph.nodes)
    if surface == "nodes-call":
        return iter(graph.nodes())
    if surface == "adj":
        return iter(graph.adj)
    raise AssertionError(surface)


@pytest.mark.parametrize("class_name", CLASSES)
@pytest.mark.parametrize("surface", ["graph", "nodes", "nodes-call", "adj"])
@pytest.mark.parametrize(
    "label_kind",
    ["int-subclass", "tuple", "tuple-subclass", "nested-tuple-subclass", "frozenset"],
)
@pytest.mark.parametrize("warm", [False, True], ids=["cold", "warm"])
def test_node_iteration_does_not_hash_or_compare_existing_labels(
    class_name, surface, label_kind, warm
):
    """Native iteration must not invoke protocols that a dict iterator skips."""
    for lib in (nx, fnx):
        armed = False
        events = []

        class Label(int):
            def __hash__(self):
                if armed:
                    events.append("hash")
                    raise LookupError("existing label was hashed")
                return int.__hash__(self)

            def __eq__(self, other):
                if armed:
                    events.append("eq")
                    raise LookupError("existing label was compared")
                return int.__eq__(self, other)

        class TupleLabel(tuple):
            def __hash__(self):
                if armed:
                    events.append("hash")
                    raise LookupError("existing tuple label was hashed")
                return tuple.__hash__(self)

            def __eq__(self, other):
                if armed:
                    events.append("eq")
                    raise LookupError("existing tuple label was compared")
                return tuple.__eq__(self, other)

        if label_kind == "int-subclass":
            labels = [Label(value) for value in range(3)]
        elif label_kind == "tuple":
            labels = [(Label(value),) for value in range(3)]
        elif label_kind == "tuple-subclass":
            labels = [TupleLabel((value,)) for value in range(3)]
        elif label_kind == "nested-tuple-subclass":
            labels = [(TupleLabel((value,)),) for value in range(3)]
        else:
            # Distinct equal-hash builtin integers force equality if an
            # incorrectly admitted frozenset is inserted into a key mirror.
            labels = [
                frozenset([Label(value * sys.hash_info.modulus)])
                for value in range(3)
            ]
        graph = getattr(lib, class_name)()
        graph.add_nodes_from(labels)
        if warm:
            list(_node_iterator(graph, surface))
        armed = True
        for _ in range(2):
            observed = list(_node_iterator(graph, surface))
            assert len(observed) == len(labels)
            assert all(actual is expected for actual, expected in zip(observed, labels))
        assert events == []


@pytest.mark.parametrize("class_name", CLASSES)
@pytest.mark.parametrize("prewarm", ["primitive", "membership", "unhashed"])
def test_warm_node_mirrors_do_not_move_reentrant_hash_into_iteration(
    class_name, prewarm
):
    """A pre-existing key/value cache must not change the callback boundary."""
    results = []
    for lib in (nx, fnx):
        graph = getattr(lib, class_name)()
        armed = False
        events = []

        class Label(int):
            def __hash__(self):
                if armed:
                    events.append("hash")
                    graph.add_node(99)
                return int.__hash__(self)

        graph.add_node(0)
        if prewarm == "primitive":
            list(graph)
        label = Label(1)
        graph.add_node(label)
        if prewarm == "membership":
            if lib is fnx:
                graph._fnx_node_key_dict()
            else:
                list(graph)
        elif prewarm == "unhashed":
            if lib is fnx:
                list(graph._fnx_unhashed_node_iter())
            else:
                list(graph)
        armed = True
        first = list(graph)
        second = list(graph.nodes)
        results.append(
            (
                [int(node) for node in first],
                [int(node) for node in second],
                first[1] is label,
                second[1] is label,
                events,
                graph.number_of_nodes(),
            )
        )
    assert results[1] == results[0]
    assert results[0][4] == []


def _iteration_tail(iterator):
    values = []
    while True:
        try:
            values.append(int(next(iterator)))
        except (StopIteration, RuntimeError) as exc:
            ended = (type(exc).__name__, exc.args)
            break
    try:
        following = ("value", int(next(iterator)))
    except (StopIteration, RuntimeError) as exc:
        following = (type(exc).__name__, exc.args)
    return values, ended, following


@pytest.mark.parametrize("class_name", CLASSES)
@pytest.mark.parametrize("surface", ["graph", "nodes"])
@pytest.mark.parametrize("size", [3, 5])
@pytest.mark.parametrize("consumed", ["one", "all", "exhausted"])
@pytest.mark.parametrize(
    "mutation",
    ["add", "remove", "replace-unseen", "replace-seen", "reinsert", "clear", "edge"],
)
def test_callback_free_node_iterators_preserve_live_mutation_behavior(
    class_name, surface, size, consumed, mutation
):
    """Retain dict cursor/resize behavior, including same-count mutations."""
    results = []
    for lib in (nx, fnx):
        armed = False

        class Label(int):
            def __hash__(self):
                if armed:
                    raise LookupError("iteration hashed an existing node")
                return int.__hash__(self)

        labels = [Label(value) for value in range(size)]
        graph = getattr(lib, class_name)()
        graph.add_nodes_from(labels)
        armed = True
        iterator = _node_iterator(graph, surface)
        if consumed == "one":
            prefix = [int(next(iterator))]
        elif consumed == "all":
            prefix = [int(next(iterator)) for _ in range(size)]
        else:
            prefix = [int(node) for node in iterator]
        armed = False
        if mutation == "add":
            graph.add_node(Label(size))
        elif mutation == "remove":
            graph.remove_node(labels[-1])
        elif mutation == "replace-unseen":
            graph.remove_node(labels[-1])
            graph.add_node(Label(size))
        elif mutation == "replace-seen":
            graph.remove_node(labels[0])
            graph.add_node(Label(size))
        elif mutation == "reinsert":
            graph.remove_node(labels[0])
            graph.add_node(labels[0])
        elif mutation == "clear":
            graph.clear()
        else:
            graph.add_edge(labels[0], labels[-1])
        armed = True
        results.append((prefix, _iteration_tail(iterator)))
    assert results[1] == results[0]


@pytest.mark.parametrize("class_name", CLASSES)
@pytest.mark.parametrize("shape", ["ints", "strings", "nested"])
@pytest.mark.parametrize("prewarm_values", [False, True])
def test_builtin_node_iteration_keeps_dict_keyiterator(
    class_name, shape, prewarm_values
):
    """Internal value iteration does not change ordinary public iterator types."""
    if shape == "ints":
        labels = [0, 1, 2]
    elif shape == "strings":
        labels = ["zero", "one", "two"]
    else:
        labels = [(value, (b"bytes", frozenset({value}), 1j)) for value in range(3)]
    graph = getattr(fnx, class_name)()
    graph.add_nodes_from(labels)
    if prewarm_values:
        assert list(graph._fnx_unhashed_node_iter()) == labels
    for surface in ("graph", "nodes", "nodes-call", "adj"):
        iterator = _node_iterator(graph, surface)
        assert type(iterator) is type(iter({}))
        assert list(iterator) == labels


@pytest.mark.parametrize("class_name", CLASSES)
def test_clear_readmits_builtin_iteration_without_losing_old_cursor_state(class_name):
    outcomes = []
    for lib in (nx, fnx):
        class Label(int):
            pass

        graph = getattr(lib, class_name)()
        graph.add_nodes_from([Label(0), Label(1), Label(2)])
        old = iter(graph)
        assert int(next(old)) == 0
        graph.clear()
        outcomes.append(_iteration_tail(old))
        graph.add_nodes_from([10, 11])
        fresh = iter(graph)
        assert type(fresh) is type(iter({}))
        assert list(fresh) == [10, 11]
    assert outcomes[1] == outcomes[0]
