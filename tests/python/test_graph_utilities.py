"""Tests for graph utility wrapper functions."""

import networkx as nx

import franken_networkx as fnx
from franken_networkx.drawing.layout import _to_nx


def test_voronoi_cells_and_stoer_wagner_match_networkx():
    graph = fnx.path_graph(5)

    assert fnx.voronoi_cells(graph, [0, 4]) == nx.voronoi_cells(nx.path_graph(5), [0, 4])
    assert fnx.stoer_wagner(graph) == nx.stoer_wagner(nx.path_graph(5))


def test_dedensify_and_quotient_graph_match_networkx():
    bipartite = fnx.complete_bipartite_graph(2, 4)
    dedensified, compressors = fnx.dedensify(bipartite, 2, prefix="aux")
    dedensified_nx, compressors_nx = nx.dedensify(_to_nx(bipartite), 2, prefix="aux")

    partition = [{0, 1}, {2, 3}]
    quotient = fnx.quotient_graph(fnx.path_graph(4), partition)
    quotient_nx = nx.quotient_graph(_to_nx(fnx.path_graph(4)), partition)

    assert sorted(_to_nx(dedensified).edges()) == sorted(dedensified_nx.edges())
    assert compressors == compressors_nx
    assert sorted(_to_nx(quotient).edges()) == sorted(quotient_nx.edges())


def test_snap_aggregation_and_full_join_match_networkx():
    graph = fnx.path_graph(4)
    for node, color in [(0, "red"), (1, "red"), (2, "blue"), (3, "blue")]:
        graph.nodes[node]["color"] = color

    graph_nx = nx.path_graph(4)
    for node, color in [(0, "red"), (1, "red"), (2, "blue"), (3, "blue")]:
        graph_nx.nodes[node]["color"] = color

    summary = fnx.snap_aggregation(graph, ["color"])
    summary_nx = nx.snap_aggregation(graph_nx, ["color"])
    joined = fnx.full_join(fnx.path_graph(2), fnx.path_graph(2), rename=("L", "R"))
    joined_nx = nx.full_join(nx.path_graph(2), nx.path_graph(2), rename=("L", "R"))

    assert sorted(_to_nx(summary).edges()) == sorted(summary_nx.edges())
    assert sorted(_to_nx(joined).edges()) == sorted(joined_nx.edges())


def test_identified_nodes_and_inverse_line_graph_match_networkx():
    path = fnx.path_graph(4)
    identified = fnx.identified_nodes(path, 1, 2)
    identified_nx = nx.identified_nodes(_to_nx(path), 1, 2)

    line = fnx.line_graph(fnx.path_graph(5))
    inverse = fnx.inverse_line_graph(line)
    inverse_nx = nx.inverse_line_graph(_to_nx(line))

    assert sorted(_to_nx(identified).edges()) == sorted(identified_nx.edges())
    assert sorted(_to_nx(inverse).edges()) == sorted(inverse_nx.edges())


def test_graph_utility_wrappers_match_networkx():
    graph = fnx.Graph()
    graph.add_edge(0, 1, weight=2)
    graph.add_edge(1, 2, weight=3)
    graph.add_edge(2, 3, weight=4)

    expected = nx.Graph()
    expected.add_edge(0, 1, weight=2)
    expected.add_edge(1, 2, weight=3)
    expected.add_edge(2, 3, weight=4)

    assert list(fnx.nodes(graph)) == list(nx.nodes(expected))
    assert list(fnx.edges(graph)) == list(nx.edges(expected))
    assert sorted(fnx.edges(graph, [1, 2])) == sorted(nx.edges(expected, [1, 2]))
    assert list(fnx.degree(graph)) == list(nx.degree(expected))
    assert dict(fnx.degree(graph, weight="weight")) == dict(nx.degree(expected, weight="weight"))
    assert tuple(fnx.neighbors(graph, 1)) == tuple(nx.neighbors(expected, 1))


def test_directed_conversion_helpers_match_networkx():
    graph = fnx.MultiGraph()
    graph.graph["name"] = "base"
    graph.add_node("a", color="red")
    graph.add_edge("a", "b", key=4, weight=2)

    expected = nx.MultiGraph()
    expected.graph["name"] = "base"
    expected.add_node("a", color="red")
    expected.add_edge("a", "b", key=4, weight=2)

    directed = fnx.to_directed(graph)
    directed_nx = nx.to_directed(expected)
    assert directed.is_directed()
    assert directed.is_multigraph()
    assert dict(directed.graph) == directed_nx.graph
    assert sorted(directed.nodes(data=True)) == sorted(directed_nx.nodes(data=True))
    assert sorted(directed.edges(keys=True, data=True)) == sorted(directed_nx.edges(keys=True, data=True))

    undirected = fnx.to_undirected(directed)
    undirected_nx = nx.to_undirected(directed_nx)
    assert not undirected.is_directed()
    assert undirected.is_multigraph()
    assert dict(undirected.graph) == undirected_nx.graph
    assert sorted(undirected.nodes(data=True)) == sorted(undirected_nx.nodes(data=True))
    assert sorted(undirected.edges(keys=True, data=True)) == sorted(undirected_nx.edges(keys=True, data=True))


def test_reverse_helper_matches_networkx():
    digraph = fnx.MultiDiGraph()
    digraph.graph["kind"] = "digraph"
    digraph.add_edge("u", "v", key=9, capacity=4)

    expected = nx.MultiDiGraph()
    expected.graph["kind"] = "digraph"
    expected.add_edge("u", "v", key=9, capacity=4)

    reversed_graph = fnx.reverse(digraph)
    reversed_nx = nx.reverse(expected)
    assert dict(reversed_graph.graph) == reversed_nx.graph
    assert sorted(reversed_graph.edges(keys=True, data=True)) == sorted(reversed_nx.edges(keys=True, data=True))
