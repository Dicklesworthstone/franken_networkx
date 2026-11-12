"""Streaming tree enumeration and multigraph routing contracts.

Both iterators use owned incremental partition frontiers, including keyed
parallel edges. Directed multigraph coverage uses an independent exhaustive
oracle because NetworkX 3.6.1 duplicates or loses parallel alternatives.
"""

from __future__ import annotations

from itertools import combinations, islice

import pytest

import franken_networkx as fnx

try:
    import networkx as nx

    HAS_NX = True
except ImportError:
    HAS_NX = False


needs_nx = pytest.mark.skipif(not HAS_NX, reason="networkx not installed")


@needs_nx
def test_spanning_tree_iterator_multigraph_yields_results():
    g = fnx.MultiGraph()
    g.add_edge(0, 1, weight=1)
    g.add_edge(1, 2, weight=1)
    trees = list(fnx.SpanningTreeIterator(g))
    assert len(trees) >= 1


@needs_nx
def test_arborescence_iterator_multidigraph_yields_results():
    g = fnx.MultiDiGraph()
    g.add_edge(0, 1, weight=1)
    g.add_edge(1, 2, weight=1)
    arbs = list(fnx.ArborescenceIterator(g))
    assert len(arbs) >= 1


def test_spanning_tree_iterator_directed_still_rejected():
    g = fnx.DiGraph()
    g.add_edge(0, 1)
    with pytest.raises(fnx.NetworkXNotImplemented, match="directed"):
        list(fnx.SpanningTreeIterator(g))


def test_arborescence_iterator_undirected_still_rejected():
    g = fnx.Graph()
    g.add_edge(0, 1)
    with pytest.raises(fnx.NetworkXNotImplemented, match="undirected"):
        list(fnx.ArborescenceIterator(g))


@needs_nx
def test_spanning_tree_iterator_simple_undirected_still_native():
    g = fnx.path_graph(4)
    trees = list(fnx.SpanningTreeIterator(g))
    assert len(trees) == 1  # path graph has exactly one spanning tree


@needs_nx
def test_arborescence_iterator_simple_digraph_still_native():
    g = fnx.DiGraph()
    g.add_edge(0, 1)
    g.add_edge(1, 2)
    arbs = list(fnx.ArborescenceIterator(g))
    assert len(arbs) >= 1


def _tree_edges(graph):
    if graph.is_directed():
        return frozenset(graph.edges())
    return frozenset(frozenset(edge) for edge in graph.edges())


@needs_nx
@pytest.mark.parametrize("minimum", [True, False])
@pytest.mark.parametrize("name,graph_type,n", [
    ("SpanningTreeIterator", "Graph", 5),
    ("ArborescenceIterator", "DiGraph", 4),
])
def test_complete_enumeration_preserves_count_weights_and_uniqueness(
    name, graph_type, n, minimum
):
    expected_graph = nx.complete_graph(n, create_using=getattr(nx, graph_type))
    for index, (u, v) in enumerate(expected_graph.edges):
        expected_graph[u][v]["cost"] = index % 5 - 2
    graph = getattr(fnx, graph_type)(expected_graph)
    expected = list(getattr(nx, name)(expected_graph, weight="cost", minimum=minimum))
    actual = list(getattr(fnx, name)(graph, weight="cost", minimum=minimum))
    edge_sets = [_tree_edges(tree) for tree in actual]
    assert len(actual) == len(expected) == len(set(edge_sets))
    assert set(edge_sets) == {_tree_edges(tree) for tree in expected}
    assert [tree.size(weight="cost") for tree in actual] == [
        tree.size(weight="cost") for tree in expected
    ]
    assert all(type(tree) is getattr(fnx, graph_type) for tree in actual)


@needs_nx
@pytest.mark.parametrize("minimum", [True, False])
@pytest.mark.parametrize("name,graph_type,n,raw_name", [
    ("SpanningTreeIterator", "Graph", 8, "spanning_tree_iterator_rust"),
    ("ArborescenceIterator", "DiGraph", 6, "arborescence_iterator_rust"),
])
def test_prefix_uses_a_bounded_partition_frontier(
    monkeypatch, name, graph_type, n, raw_name, minimum
):
    def eager_enumeration_forbidden(*args, **kwargs):
        raise AssertionError("a prefix must not enumerate the entire result space")

    monkeypatch.setattr(fnx._fnx, raw_name, eager_enumeration_forbidden)
    selection_name = (
        "partition_spanning_tree" if graph_type == "Graph"
        else "minimum_spanning_arborescence" if minimum
        else "maximum_spanning_arborescence"
    )
    select = getattr(fnx, selection_name)
    calls = 0

    def counted_selection(*args, **kwargs):
        nonlocal calls
        calls += 1
        assert calls <= 1 + 3 * n
        return select(*args, **kwargs)

    monkeypatch.setattr(fnx, selection_name, counted_selection)
    graph = fnx.complete_graph(n, create_using=getattr(fnx, graph_type))
    trees = list(islice(getattr(fnx, name)(graph, minimum=minimum), 3))
    assert len(trees) == 3
    assert len({_tree_edges(tree) for tree in trees}) == 3
    assert 1 <= calls <= 1 + 3 * n
    predicate = fnx.is_tree if graph_type == "Graph" else fnx.is_arborescence
    assert all(predicate(tree) for tree in trees)


@needs_nx
@pytest.mark.parametrize("name,graph_type", [
    ("SpanningTreeIterator", "Graph"),
    ("ArborescenceIterator", "DiGraph"),
    ("SpanningTreeIterator", "MultiGraph"),
    ("ArborescenceIterator", "MultiDiGraph"),
])
def test_iterator_captures_input_and_preserves_attributes(name, graph_type):
    graph = getattr(fnx, graph_type)()
    graph.graph["description"] = "snapshot"
    graph.add_node("a", label="first")
    graph.add_node("b", label="second")
    graph.add_edge("a", "b", cost=3, payload={"tags": ["original"]})
    reference = getattr(nx, graph_type)(graph)
    expected_iterator = getattr(nx, name)(reference, weight="cost")
    iterator = getattr(fnx, name)(graph, weight="cost")
    graph.clear()
    reference.clear()
    tree = next(iter(iterator))
    expected = next(iter(expected_iterator))
    assert dict(tree.graph) == dict(expected.graph)
    assert dict(tree.nodes(data=True)) == dict(expected.nodes(data=True))
    data = next(iter(tree.edges(data=True)))[-1]
    assert data == {"cost": 3, "payload": {"tags": ["original"]}}


@needs_nx
@pytest.mark.parametrize("minimum", [True, False])
def test_arborescence_initial_partition_remains_enforced(minimum):
    expected_graph = nx.complete_graph(4, create_using=nx.DiGraph)
    for index, (u, v) in enumerate(expected_graph.edges):
        expected_graph[u][v]["cost"] = index + 1
    included = [(0, 1)]
    excluded = [(2, 3)]
    graph = fnx.DiGraph(expected_graph)
    iterator = fnx.ArborescenceIterator(
        graph, weight="cost", minimum=minimum,
        init_partition=(iter(included), iter(excluded)),
    )
    actual = list(iterator)
    expected = list(nx.ArborescenceIterator(
        expected_graph, weight="cost", minimum=minimum,
        init_partition=(included, excluded),
    ))
    assert {_tree_edges(tree) for tree in actual} == {
        _tree_edges(tree) for tree in expected
    }
    assert [tree.size(weight="cost") for tree in actual] == [
        tree.size(weight="cost") for tree in expected
    ]
    assert all(tree.has_edge(0, 1) and not tree.has_edge(2, 3) for tree in actual)


@needs_nx
@pytest.mark.parametrize("minimum", [True, False])
def test_spanning_iterator_nan_policy(minimum):
    graph = fnx.Graph()
    graph.add_weighted_edges_from([(0, 1, 1), (1, 2, 2), (0, 2, float("nan"))])
    with pytest.raises(ValueError, match="NaN"):
        iter(fnx.SpanningTreeIterator(graph, minimum=minimum))
    trees = list(fnx.SpanningTreeIterator(graph, minimum=minimum, ignore_nan=True))
    assert len(trees) == 1
    assert _tree_edges(trees[0]) == frozenset((frozenset((0, 1)), frozenset((1, 2))))


@needs_nx
@pytest.mark.parametrize("edges", [[], [(0, 1)], [(0, 1), (2, 3)]])
def test_spanning_iterator_degenerate_graphs_match_reference(edges):
    actual = list(fnx.SpanningTreeIterator(fnx.Graph(edges)))
    expected = list(nx.SpanningTreeIterator(nx.Graph(edges)))
    assert [set(tree) for tree in actual] == [set(tree) for tree in expected]
    assert [_tree_edges(tree) for tree in actual] == [
        _tree_edges(tree) for tree in expected
    ]


def _keyed_tree_edges(graph):
    return frozenset((frozenset((u, v)), key) for u, v, key in graph.edges(keys=True))


@needs_nx
@pytest.mark.parametrize("minimum", [True, False])
@pytest.mark.parametrize("weight_kind", ["int", "fraction", "large_int"])
def test_multigraph_spanning_trees_preserve_keys_costs_and_native_outputs(
    monkeypatch, minimum, weight_kind
):
    from fractions import Fraction

    reference = nx.MultiGraph(description="parallel alternatives")
    reference.add_node("s", role="source")
    reference.add_node(("via", 1), role="intermediate")
    reference.add_node(42, role="target")
    edges = [
        ("s", ("via", 1), "fast", 1),
        ("s", ("via", 1), ("slow", 2), 3),
        (("via", 1), 42, "last", 2),
        ("s", 42, 17, 4),
        ("s", "s", "loop", -10),
    ]
    for u, v, key, value in edges:
        cost = (
            Fraction(value, 3) if weight_kind == "fraction"
            else 2**60 + value if weight_kind == "large_int"
            else value
        )
        reference.add_edge(u, v, key=key, cost=cost, payload={"key": key})
    graph = fnx.MultiGraph(reference)
    expected = list(nx.SpanningTreeIterator(reference, weight="cost", minimum=minimum))

    def delegation_forbidden(*args, **kwargs):
        raise AssertionError("multigraph spanning trees must use the owned frontier")

    monkeypatch.setattr(nx, "SpanningTreeIterator", delegation_forbidden)
    monkeypatch.setattr(fnx, "_networkx_graph_for_parity", delegation_forbidden)
    actual = list(fnx.SpanningTreeIterator(graph, weight="cost", minimum=minimum))
    actual_edges = [_keyed_tree_edges(tree) for tree in actual]
    assert len(actual) == len(expected) == len(set(actual_edges)) == 5
    assert set(actual_edges) == {_keyed_tree_edges(tree) for tree in expected}
    # Equal-weight tie order is unspecified. Exact integer costs must still
    # order the alternatives even when float Graph.size() would round them.
    costs = [sum(data["cost"] for *_, data in tree.edges(data=True)) for tree in actual]
    assert costs == sorted(costs, reverse=not minimum)
    assert sorted(costs) == sorted(
        sum(data["cost"] for *_, data in tree.edges(data=True)) for tree in expected
    )
    for tree in actual:
        assert type(tree) is fnx.MultiGraph
        assert fnx.is_tree(tree)
        assert tree.graph == reference.graph
        assert dict(tree.nodes(data=True)) == dict(reference.nodes(data=True))
        for u, v, key, attrs in tree.edges(keys=True, data=True):
            assert attrs == reference.edges[u, v, key]
            assert type(attrs["cost"]) is type(reference.edges[u, v, key]["cost"])
    assert all(
        "SpanningTreeIterators super secret partition attribute name" not in attrs
        for *_, attrs in graph.edges(data=True)
    )


@needs_nx
@pytest.mark.parametrize("minimum", [True, False])
def test_multigraph_spanning_tree_prefix_keeps_a_bounded_frontier(monkeypatch, minimum):
    n = 7
    graph = fnx.MultiGraph()
    for u in range(n):
        for v in range(u + 1, n):
            graph.add_edge(u, v, key="first", weight=1)
            graph.add_edge(u, v, key="second", weight=2)
    select = fnx.partition_spanning_tree
    calls = 0

    def counted_selection(*args, **kwargs):
        nonlocal calls
        calls += 1
        assert calls <= 1 + 3 * (n - 1)
        return select(*args, **kwargs)

    def delegation_forbidden(*args, **kwargs):
        raise AssertionError("a multigraph prefix must use the owned partition frontier")

    monkeypatch.setattr(fnx, "partition_spanning_tree", counted_selection)
    monkeypatch.setattr(nx, "SpanningTreeIterator", delegation_forbidden)
    iterator = iter(fnx.SpanningTreeIterator(graph, minimum=minimum))
    trees = list(islice(iterator, 3))
    assert len({_keyed_tree_edges(tree) for tree in trees}) == 3
    assert all(type(tree) is fnx.MultiGraph and fnx.is_tree(tree) for tree in trees)
    assert 1 <= calls <= 1 + 3 * (n - 1)
    assert len(iterator.partition_queue) <= 1 + 3 * (n - 1)


@needs_nx
@pytest.mark.parametrize("minimum", [True, False])
@pytest.mark.parametrize("shape", ["empty", "singleton", "disconnected", "nan"])
def test_multigraph_spanning_iterator_boundary_parity(shape, minimum):
    reference = nx.MultiGraph()
    if shape == "singleton":
        reference.add_node("alone")
        reference.add_edge("alone", "alone", key="loop", weight=-1)
    elif shape == "disconnected":
        reference.add_nodes_from(range(4))
        reference.add_edge(0, 1, key="a", weight=1)
        reference.add_edge(2, 3, key="b", weight=2)
    elif shape == "nan":
        reference.add_edge(0, 1, key="valid", weight=1)
        reference.add_edge(0, 1, key="invalid", weight=float("nan"))
        with pytest.raises(ValueError, match="NaN"):
            iter(fnx.SpanningTreeIterator(fnx.MultiGraph(reference), minimum=minimum))
    expected = list(nx.SpanningTreeIterator(reference, minimum=minimum, ignore_nan=True))
    actual = list(fnx.SpanningTreeIterator(
        fnx.MultiGraph(reference), minimum=minimum, ignore_nan=True
    ))
    assert [list(tree) for tree in actual] == [list(tree) for tree in expected]
    assert [_keyed_tree_edges(tree) for tree in actual] == [
        _keyed_tree_edges(tree) for tree in expected
    ]
    assert all(type(tree) is fnx.MultiGraph for tree in actual)


@needs_nx
@pytest.mark.parametrize("minimum", [True, False])
@pytest.mark.parametrize("weight_kind", ["int", "fraction", "float"])
def test_directed_arborescences_use_owned_frontier(monkeypatch, minimum, weight_kind):
    from fractions import Fraction

    reference = nx.complete_graph(4, create_using=nx.DiGraph)
    reference.graph["title"] = "arborescences"
    for node in reference:
        reference.nodes[node]["label"] = f"node-{node}"
    for index, (u, v, attrs) in enumerate(reference.edges(data=True)):
        value = index % 7 - 2
        attrs["cost"] = (
            Fraction(value, 3) if weight_kind == "fraction"
            else value / 4 if weight_kind == "float"
            else value
        )
        attrs["payload"] = {"edge": (u, v)}
    graph = fnx.DiGraph(reference)
    original = [(u, v, dict(attrs)) for u, v, attrs in graph.edges(data=True)]
    expected = list(nx.ArborescenceIterator(reference, weight="cost", minimum=minimum))

    def scheduler_forbidden(*args, **kwargs):
        raise AssertionError("simple directed enumeration must own its partition frontier")

    monkeypatch.setattr(nx, "ArborescenceIterator", scheduler_forbidden)
    monkeypatch.setattr(nx.algorithms.tree.branchings, "ArborescenceIterator", scheduler_forbidden)
    actual = list(fnx.ArborescenceIterator(graph, weight="cost", minimum=minimum))
    assert len(actual) == len(expected) == 64
    edge_sets = [_tree_edges(tree) for tree in actual]
    assert len(set(edge_sets)) == len(actual)
    assert set(edge_sets) == {_tree_edges(tree) for tree in expected}
    assert [tree.size(weight="cost") for tree in actual] == [
        tree.size(weight="cost") for tree in expected
    ]
    by_edges = {_tree_edges(tree): tree for tree in expected}
    for tree in actual:
        oracle = by_edges[_tree_edges(tree)]
        assert type(tree) is fnx.DiGraph
        assert fnx.is_arborescence(tree)
        assert dict(tree.graph) == oracle.graph
        assert dict(tree.nodes(data=True)) == dict(oracle.nodes(data=True))
        for u, v, attrs in tree.edges(data=True):
            assert dict(attrs) == oracle.edges[u, v]
            assert type(attrs["cost"]) is type(oracle.edges[u, v]["cost"])
    assert [(u, v, dict(attrs)) for u, v, attrs in graph.edges(data=True)] == original


@needs_nx
@pytest.mark.parametrize("minimum", [True, False])
def test_directed_arborescence_included_parent_survives_cycle_contraction(monkeypatch, minimum):
    reference = nx.DiGraph()
    reference.add_weighted_edges_from([
        (0, 1, 9), (1, 2, 8), (2, 0, 7),
        (3, 0, 2), (3, 1, 3), (3, 2, 4), (2, 3, 1),
    ])
    initial = ([(0, 1)], [(3, 2)])
    expected = list(nx.ArborescenceIterator(reference, minimum=minimum, init_partition=initial))
    graph = fnx.DiGraph(reference)

    def scheduler_forbidden(*args, **kwargs):
        raise AssertionError("the incoming-edge constraint must be owned")

    monkeypatch.setattr(nx, "ArborescenceIterator", scheduler_forbidden)
    iterator = fnx.ArborescenceIterator(
        graph, minimum=minimum,
        init_partition=(iter(initial[0]), iter(initial[1])),
    )
    actual = list(iterator)
    assert {_tree_edges(tree) for tree in actual} == {_tree_edges(tree) for tree in expected}
    assert [tree.size(weight="weight") for tree in actual] == [
        tree.size(weight="weight") for tree in expected
    ]
    assert all(tree.has_edge(0, 1) and not tree.has_edge(3, 2) for tree in actual)


@needs_nx
@pytest.mark.parametrize("minimum", [True, False])
def test_directed_arborescence_prefix_uses_bounded_owned_selection(monkeypatch, minimum):
    graph = fnx.complete_graph(7, create_using=fnx.DiGraph)
    name = "minimum_spanning_arborescence" if minimum else "maximum_spanning_arborescence"
    select = getattr(fnx, name)
    calls = 0

    def bounded_selection(*args, **kwargs):
        nonlocal calls
        calls += 1
        assert calls <= 1 + 3 * len(graph)
        return select(*args, **kwargs)

    def scheduler_forbidden(*args, **kwargs):
        raise AssertionError("a prefix must not invoke an upstream or exhaustive scheduler")

    monkeypatch.setattr(fnx, name, bounded_selection)
    monkeypatch.setattr(nx, "ArborescenceIterator", scheduler_forbidden)
    monkeypatch.setattr(fnx._fnx, "arborescence_iterator_rust", scheduler_forbidden)
    iterator = iter(fnx.ArborescenceIterator(graph, minimum=minimum))
    trees = list(islice(iterator, 3))
    assert len({_tree_edges(tree) for tree in trees}) == 3
    assert all(type(tree) is fnx.DiGraph and fnx.is_arborescence(tree) for tree in trees)
    assert 1 <= calls <= 1 + 3 * len(graph)
    assert len(iterator.partition_queue) <= 1 + 3 * (len(graph) - 1)


@needs_nx
@pytest.mark.parametrize("graph_type", ["DiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("shape", ["empty", "singleton", "disconnected", "infeasible_partition"])
def test_directed_arborescence_initial_state_matches_reference(shape, graph_type):
    reference = getattr(nx, graph_type)()
    initial = None
    if shape == "singleton":
        reference.add_node("only")
    elif shape == "disconnected":
        reference.add_nodes_from(range(3))
        reference.add_edge(0, 1)
    elif shape == "infeasible_partition":
        reference.add_edges_from([(0, 1), (1, 2)])
        initial = ([], [(0, 1)])

    def consume(factory, graph):
        try:
            return [list(tree.edges) for tree in factory(graph, init_partition=initial)]
        except Exception as exc:
            return type(exc).__name__, str(exc)

    assert consume(fnx.ArborescenceIterator, getattr(fnx, graph_type)(reference)) == consume(
        nx.ArborescenceIterator, reference
    )


def _exhaustive_keyed_arborescences(graph, included=(), excluded=()):
    """Small independent oracle, without any arborescence selector/scheduler."""
    included, excluded = set(included), set(excluded)
    result = {}
    for edges in combinations(graph.edges(keys=True), len(graph) - 1):
        signature = frozenset(edges)
        if not included <= signature or excluded & signature:
            continue
        candidate = nx.MultiDiGraph()
        candidate.add_nodes_from(graph)
        candidate.add_edges_from(edges)
        if nx.is_arborescence(candidate):
            result[signature] = sum(graph.edges[edge].get("cost", 1) for edge in edges)
    return result


@needs_nx
@pytest.mark.parametrize("minimum", [True, False])
@pytest.mark.parametrize("weight_kind", ["int", "large_int", "fraction", "decimal", "float"])
def test_multidigraph_arborescences_enumerate_every_keyed_choice(
    monkeypatch, minimum, weight_kind
):
    from decimal import Decimal
    from fractions import Fraction

    reference = nx.MultiDiGraph(description="keyed arborescences")
    reference.add_nodes_from([("s", {"role": "source"}), (("via", 1), {}), (42, {})])
    for u, v, key, value in [
        ("s", ("via", 1), "fast", -1),
        ("s", ("via", 1), ("slow", 2), 3),
        (("via", 1), 42, "last", 2),
        ("s", 42, 17, 4),
        (42, "s", "back", 0),
        (42, ("via", 1), "reverse", 1),
        (("via", 1), "s", "return", 5),
        ("s", "s", "loop", -10),
    ]:
        cost = (
            2**60 + value if weight_kind == "large_int"
            else Fraction(value, 3) if weight_kind == "fraction"
            else Decimal(value) / 8 if weight_kind == "decimal"
            else value / 4 if weight_kind == "float"
            else value
        )
        reference.add_edge(u, v, key=key, cost=cost, payload={"key": key})
    expected = _exhaustive_keyed_arborescences(reference)
    graph = fnx.MultiDiGraph(reference)
    original = [(u, v, key, dict(attrs)) for u, v, key, attrs in graph.edges(keys=True, data=True)]

    def scheduler_forbidden(*args, **kwargs):
        raise AssertionError("parallel arborescences must use the owned keyed frontier")

    monkeypatch.setattr(nx, "ArborescenceIterator", scheduler_forbidden)
    monkeypatch.setattr(nx.algorithms.tree.branchings, "ArborescenceIterator", scheduler_forbidden)
    actual = list(fnx.ArborescenceIterator(graph, weight="cost", minimum=minimum))
    signatures = [frozenset(tree.edges(keys=True)) for tree in actual]
    assert len(actual) == len(set(signatures)) == len(expected)
    assert set(signatures) == set(expected)
    costs = [sum(attrs["cost"] for *_, attrs in tree.edges(data=True)) for tree in actual]
    assert costs == sorted(expected.values(), reverse=not minimum)
    for tree in actual:
        assert type(tree) is fnx.MultiDiGraph
        assert fnx.is_arborescence(tree)
        # Branching selectors discard graph/node metadata but preserve edge
        # attributes. Key restoration must keep precisely that same policy.
        assert tree.graph == {}
        assert dict(tree.nodes(data=True)) == dict.fromkeys(reference, {})
        for u, v, key, attrs in tree.edges(keys=True, data=True):
            assert dict(attrs) == reference.edges[u, v, key]
            assert type(attrs["cost"]) is type(reference.edges[u, v, key]["cost"])
    assert list(graph.edges(keys=True, data=True)) == original


@needs_nx
@pytest.mark.parametrize("minimum", [True, False])
@pytest.mark.parametrize("case", ["include", "exclude", "overlap", "unique_pair"])
def test_multidigraph_arborescence_initial_keyed_constraints(minimum, case):
    reference = nx.MultiDiGraph()
    for u, v, key, cost in [
        (0, 1, "a", 1), (0, 1, "b", 2), (1, 2, "c", 3),
        (0, 2, "d", 4), (2, 0, "e", 5), (2, 1, "f", 6),
    ]:
        reference.add_edge(u, v, key=key, cost=cost)
    initial = {
        "include": ([(0, 1, "b")], [(2, 1, "f")]),
        "exclude": ([], [(0, 1, "a")]),
        "overlap": ([(0, 1, "a")], [(0, 1, "a")]),
        "unique_pair": ([(1, 2)], [(2, 0)]),
    }[case]
    included = set(initial[0]) - set(initial[1])
    excluded = set(initial[1])
    if case == "unique_pair":
        included, excluded = {(1, 2, "c")}, {(2, 0, "e")}
    expected = _exhaustive_keyed_arborescences(reference, included, excluded)
    actual = list(fnx.ArborescenceIterator(
        fnx.MultiDiGraph(reference), weight="cost", minimum=minimum,
        init_partition=(iter(initial[0]), iter(initial[1])),
    ))
    signatures = [frozenset(tree.edges(keys=True)) for tree in actual]
    assert len(signatures) == len(set(signatures)) == len(expected)
    assert set(signatures) == set(expected)
    assert [sum(d["cost"] for *_, d in tree.edges(data=True)) for tree in actual] == sorted(
        expected.values(), reverse=not minimum
    )


@needs_nx
@pytest.mark.parametrize("minimum", [True, False])
@pytest.mark.parametrize("included", [True, False])
def test_multidigraph_arborescence_parallel_initial_pairs_require_keys(minimum, included):
    graph = fnx.MultiDiGraph()
    graph.add_edge(0, 1, key="a")
    graph.add_edge(0, 1, key="b")
    initial = ([(0, 1)], []) if included else ([], [(0, 1)])
    with pytest.raises(ValueError, match=r"require \(u, v, key\) triples"):
        iter(fnx.ArborescenceIterator(graph, minimum=minimum, init_partition=initial))


@needs_nx
@pytest.mark.parametrize("minimum", [True, False])
@pytest.mark.parametrize("included,excluded", [
    ([(0, 1, "missing")], []),
    ([(0, 1, "a"), (2, 1, "e")], []),
    ([(0, 1, "a"), (1, 0, "d")], []),
    ([], [(0, 1, "a"), (0, 1, "b"), (1, 0, "d"), (2, 1, "e")]),
])
def test_multidigraph_arborescence_infeasible_initial_keys(minimum, included, excluded):
    graph = fnx.MultiDiGraph()
    graph.add_edges_from([
        (0, 1, "a"), (0, 1, "b"), (1, 2, "c"), (1, 0, "d"), (2, 1, "e"),
    ])
    with pytest.raises(fnx.NetworkXException, match="No .* spanning arborescence"):
        iter(fnx.ArborescenceIterator(
            graph, minimum=minimum, init_partition=(included, excluded)
        ))


@needs_nx
@pytest.mark.parametrize("minimum", [True, False])
def test_multidigraph_arborescence_prefix_keeps_bounded_owned_frontier(monkeypatch, minimum):
    n = 7
    graph = fnx.MultiDiGraph()
    for u in range(n):
        for v in range(n):
            if u != v:
                graph.add_edge(u, v, key="first", weight=1)
                graph.add_edge(u, v, key="second", weight=2)
    name = "minimum_spanning_arborescence" if minimum else "maximum_spanning_arborescence"
    select = getattr(fnx, name)
    calls = 0

    def bounded_selection(*args, **kwargs):
        nonlocal calls
        calls += 1
        assert calls <= 1 + 3 * (n - 1)
        return select(*args, **kwargs)

    def scheduler_forbidden(*args, **kwargs):
        raise AssertionError("prefix enumeration must remain lazy and owned")

    monkeypatch.setattr(fnx, name, bounded_selection)
    monkeypatch.setattr(nx, "ArborescenceIterator", scheduler_forbidden)
    monkeypatch.setattr(fnx._fnx, "arborescence_iterator_rust", scheduler_forbidden)
    iterator = fnx.ArborescenceIterator(graph, minimum=minimum)
    trees = list(islice(iterator, 3))
    assert len({frozenset(tree.edges(keys=True)) for tree in trees}) == 3
    assert all(type(tree) is fnx.MultiDiGraph and fnx.is_arborescence(tree) for tree in trees)
    assert 1 <= calls <= 1 + 3 * (n - 1)
    assert len(iterator.partition_queue) <= 1 + 3 * (n - 1)


@needs_nx
def test_multidigraph_arborescence_private_markers_do_not_replace_user_attributes():
    marker = "ArborescenceIterators super secret partition attribute name"
    graph = fnx.MultiDiGraph()
    for key, cost in [("a", 1), (("b", 2), 2)]:
        graph.add_edge(0, 1, key=key, cost=cost)
        graph.edges[0, 1, key].update({
            marker: "user partition data",
            marker + "_ original edge key": "user edge identity",
        })
    iterator = iter(fnx.ArborescenceIterator(graph, weight="cost"))
    first = next(iterator)
    assert set(first.edges[0, 1, "a"]) == set(graph.edges[0, 1, "a"])
    assert first.edges[0, 1, "a"] == graph.edges[0, 1, "a"]
    # Reinitialization must not accumulate markers in the stored snapshot.
    trees = list(iter(iterator))
    assert [next(iter(tree.edges(keys=True)))[2] for tree in trees] == ["a", ("b", 2)]
    for tree in trees:
        for u, v, key, attrs in tree.edges(keys=True, data=True):
            assert attrs == graph.edges[u, v, key]
