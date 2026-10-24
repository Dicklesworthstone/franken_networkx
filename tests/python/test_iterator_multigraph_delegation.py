"""Streaming tree enumeration and multigraph delegation contracts.

Simple graphs use native tree selection with an incremental partition
frontier. Multigraphs retain the reference scheduler's keyed-edge semantics.
"""

from __future__ import annotations

from itertools import islice

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
