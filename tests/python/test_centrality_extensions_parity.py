import math

import pytest

import franken_networkx as fnx

nx = pytest.importorskip("networkx")


def _assert_mapping_close(actual, expected, tol=1e-12):
    assert set(actual) == set(expected)
    for node in expected:
        assert math.isclose(actual[node], expected[node], rel_tol=tol, abs_tol=tol)


def test_load_centrality_native_unweighted_matches_networkx():
    graph = fnx.cycle_graph(4)

    actual = fnx.load_centrality(graph)
    expected = nx.load_centrality(nx.cycle_graph(4))

    _assert_mapping_close(actual, expected)
    assert math.isclose(fnx.load_centrality(graph, v=1), expected[1], rel_tol=1e-12, abs_tol=1e-12)


def test_load_centrality_weighted_fallback_matches_networkx():
    graph = fnx.Graph()
    graph.add_edge("a", "b", weight=2.0)
    graph.add_edge("b", "c", weight=1.0)
    graph.add_edge("a", "c", weight=5.0)

    expected_graph = nx.Graph()
    expected_graph.add_edge("a", "b", weight=2.0)
    expected_graph.add_edge("b", "c", weight=1.0)
    expected_graph.add_edge("a", "c", weight=5.0)

    actual = fnx.load_centrality(graph, weight="weight")
    expected = nx.load_centrality(expected_graph, weight="weight")

    _assert_mapping_close(actual, expected)


def test_second_order_centrality_native_unweighted_matches_networkx():
    graph = fnx.path_graph(4)

    actual = fnx.second_order_centrality(graph)
    expected = nx.second_order_centrality(nx.path_graph(4))

    _assert_mapping_close(actual, expected)


def test_second_order_centrality_weighted_fallback_matches_networkx():
    graph = fnx.path_graph(4)
    graph[0][1]["weight"] = 2.0

    expected_graph = nx.path_graph(4)
    expected_graph[0][1]["weight"] = 2.0

    actual = fnx.second_order_centrality(graph)
    expected = nx.second_order_centrality(expected_graph)

    _assert_mapping_close(actual, expected)


def test_group_closeness_centrality_native_and_directed_fallback_match_networkx():
    undirected = fnx.path_graph(4)
    expected_undirected = nx.path_graph(4)
    assert math.isclose(
        fnx.group_closeness_centrality(undirected, {1}),
        nx.group_closeness_centrality(expected_undirected, {1}),
        rel_tol=1e-12,
        abs_tol=1e-12,
    )

    directed = fnx.DiGraph()
    directed.add_edges_from([(0, 1), (1, 2), (2, 3)])
    expected_directed = nx.DiGraph([(0, 1), (1, 2), (2, 3)])
    assert math.isclose(
        fnx.group_closeness_centrality(directed, {1}),
        nx.group_closeness_centrality(expected_directed, {1}),
        rel_tol=1e-12,
        abs_tol=1e-12,
    )


def test_group_betweenness_centrality_native_and_fallback_match_networkx():
    graph = fnx.path_graph(4)
    expected_graph = nx.path_graph(4)

    assert math.isclose(
        fnx.group_betweenness_centrality(graph, {1}, normalized=True),
        nx.group_betweenness_centrality(expected_graph, {1}, normalized=True),
        rel_tol=1e-12,
        abs_tol=1e-12,
    )
    assert math.isclose(
        fnx.group_betweenness_centrality(graph, {1}, normalized=False),
        nx.group_betweenness_centrality(expected_graph, {1}, normalized=False),
        rel_tol=1e-12,
        abs_tol=1e-12,
    )
    assert math.isclose(
        fnx.group_betweenness_centrality(graph, {1}, endpoints=True),
        nx.group_betweenness_centrality(expected_graph, {1}, endpoints=True),
        rel_tol=1e-12,
        abs_tol=1e-12,
    )


def test_communicability_betweenness_centrality_matches_networkx():
    graph = fnx.path_graph(4)

    actual = fnx.communicability_betweenness_centrality(graph)
    expected = nx.communicability_betweenness_centrality(nx.path_graph(4))

    _assert_mapping_close(actual, expected)


def test_percolation_centrality_honors_attribute_and_states():
    graph = fnx.path_graph(4)
    for node, value in [(0, 0.1), (1, 0.3), (2, 0.7), (3, 1.0)]:
        graph.nodes[node]["custom_state"] = value

    expected_graph = nx.path_graph(4)
    for node, value in [(0, 0.1), (1, 0.3), (2, 0.7), (3, 1.0)]:
        expected_graph.nodes[node]["custom_state"] = value

    actual_attr = fnx.percolation_centrality(graph, attribute="custom_state")
    expected_attr = nx.percolation_centrality(expected_graph, attribute="custom_state")
    _assert_mapping_close(actual_attr, expected_attr)

    states = {0: 0.1, 1: 0.3, 2: 0.7, 3: 1.0}
    actual_states = fnx.percolation_centrality(graph, states=states)
    expected_states = nx.percolation_centrality(expected_graph, states=states)
    _assert_mapping_close(actual_states, expected_states)
