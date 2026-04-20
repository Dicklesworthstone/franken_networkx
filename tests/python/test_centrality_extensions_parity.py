import math

import numpy as np
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


def test_load_centrality_weighted_fallback_avoids_delegation(monkeypatch):
    graph = fnx.Graph()
    graph.add_edge("a", "b", weight=2.0)
    graph.add_edge("b", "c", weight=1.0)
    graph.add_edge("a", "c", weight=5.0)

    expected_graph = nx.Graph()
    expected_graph.add_edge("a", "b", weight=2.0)
    expected_graph.add_edge("b", "c", weight=1.0)
    expected_graph.add_edge("a", "c", weight=5.0)
    expected = nx.load_centrality(expected_graph, weight="weight", cutoff=3.0)

    monkeypatch.setattr(
        nx,
        "load_centrality",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("delegated")),
    )

    actual = fnx.load_centrality(graph, weight="weight", cutoff=3.0)
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


def test_second_order_centrality_weighted_fallback_avoids_delegation(monkeypatch):
    graph = fnx.path_graph(4)
    graph[0][1]["weight"] = 2.0

    expected_graph = nx.path_graph(4)
    expected_graph[0][1]["weight"] = 2.0
    expected = nx.second_order_centrality(expected_graph)

    monkeypatch.setattr(
        nx,
        "second_order_centrality",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("delegated")),
    )

    actual = fnx.second_order_centrality(graph)
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


def test_group_closeness_centrality_directed_fallback_avoids_delegation(monkeypatch):
    directed = fnx.DiGraph()
    directed.add_edges_from([(0, 1), (1, 2), (2, 3)])

    expected_directed = nx.DiGraph([(0, 1), (1, 2), (2, 3)])
    expected = nx.group_closeness_centrality(expected_directed, {1})

    monkeypatch.setattr(
        nx,
        "group_closeness_centrality",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("delegated")),
    )

    actual = fnx.group_closeness_centrality(directed, {1})
    assert math.isclose(actual, expected, rel_tol=1e-12, abs_tol=1e-12)


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


def test_group_betweenness_centrality_endpoints_fallback_avoids_delegation(monkeypatch):
    graph = fnx.path_graph(4)
    expected_graph = nx.path_graph(4)
    expected = nx.group_betweenness_centrality(expected_graph, {1}, endpoints=True)

    monkeypatch.setattr(
        nx,
        "group_betweenness_centrality",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("delegated")),
    )

    actual = fnx.group_betweenness_centrality(graph, {1}, endpoints=True)
    assert math.isclose(actual, expected, rel_tol=1e-12, abs_tol=1e-12)


def test_betweenness_centrality_subset_native_matches_networkx_and_avoids_delegation(
    monkeypatch,
):
    graph = fnx.path_graph(4)
    expected_graph = nx.path_graph(4)
    expected = nx.betweenness_centrality_subset(
        expected_graph,
        [0, 1],
        [2, 3],
        normalized=True,
    )

    def fail(*args, **kwargs):
        raise AssertionError("delegated to networkx.betweenness_centrality_subset")

    monkeypatch.setattr(nx, "betweenness_centrality_subset", fail)
    actual = fnx.betweenness_centrality_subset(
        graph,
        [0, 1],
        [2, 3],
        normalized=True,
    )
    _assert_mapping_close(actual, expected)


def test_edge_betweenness_centrality_subset_native_matches_networkx_and_avoids_delegation(
    monkeypatch,
):
    graph = fnx.cycle_graph(4)
    expected_graph = nx.cycle_graph(4)
    expected = nx.edge_betweenness_centrality_subset(
        expected_graph,
        [0, 1],
        [2, 3],
        normalized=True,
    )

    def fail(*args, **kwargs):
        raise AssertionError(
            "delegated to networkx.edge_betweenness_centrality_subset"
        )

    monkeypatch.setattr(nx, "edge_betweenness_centrality_subset", fail)
    actual = fnx.edge_betweenness_centrality_subset(
        graph,
        [0, 1],
        [2, 3],
        normalized=True,
    )
    _assert_mapping_close(actual, expected)


def test_communicability_betweenness_centrality_matches_networkx():
    graph = fnx.path_graph(4)

    actual = fnx.communicability_betweenness_centrality(graph)
    expected = nx.communicability_betweenness_centrality(nx.path_graph(4))

    _assert_mapping_close(actual, expected)


def test_edge_load_centrality_matches_networkx():
    graph = fnx.cycle_graph(4)
    expected = nx.edge_load_centrality(nx.cycle_graph(4))
    actual = fnx.edge_load_centrality(graph)
    _assert_mapping_close(actual, expected)


def test_edge_current_flow_betweenness_centrality_matches_networkx_without_fallback(
    monkeypatch,
):
    graph = fnx.Graph()
    graph.add_edge(0, 1, weight=2.0)
    graph.add_edge(1, 2, weight=3.0)
    graph.add_edge(0, 2, weight=5.0)
    graph.add_edge(2, 3, weight=1.0)

    expected_graph = nx.Graph()
    expected_graph.add_edge(0, 1, weight=2.0)
    expected_graph.add_edge(1, 2, weight=3.0)
    expected_graph.add_edge(0, 2, weight=5.0)
    expected_graph.add_edge(2, 3, weight=1.0)

    expected = nx.edge_current_flow_betweenness_centrality(
        expected_graph,
        normalized=True,
        weight="weight",
        dtype=np.float32,
        solver="cg",
    )

    monkeypatch.setattr(
        nx,
        "edge_current_flow_betweenness_centrality",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("delegated")),
    )

    actual = fnx.edge_current_flow_betweenness_centrality(
        graph,
        normalized=True,
        weight="weight",
        dtype=np.float32,
        solver="cg",
    )
    _assert_mapping_close(actual, expected, tol=1e-6)


def test_edge_current_flow_betweenness_centrality_weight_none_matches_networkx():
    graph = fnx.Graph()
    graph.add_edge(0, 1, weight=10.0)
    graph.add_edge(1, 2, weight=10.0)
    graph.add_edge(0, 2, weight=1.0)

    expected_graph = nx.Graph()
    expected_graph.add_edge(0, 1, weight=10.0)
    expected_graph.add_edge(1, 2, weight=10.0)
    expected_graph.add_edge(0, 2, weight=1.0)

    actual = fnx.edge_current_flow_betweenness_centrality(graph, weight=None)
    expected = nx.edge_current_flow_betweenness_centrality(expected_graph, weight=None)
    _assert_mapping_close(actual, expected)


def test_edge_current_flow_betweenness_centrality_multigraph_matches_networkx():
    graph = fnx.MultiGraph()
    graph.add_edge(0, 1, weight=1.0)
    graph.add_edge(0, 1, weight=3.0)
    graph.add_edge(1, 2, weight=2.0)

    expected_graph = nx.MultiGraph()
    expected_graph.add_edge(0, 1, weight=1.0)
    expected_graph.add_edge(0, 1, weight=3.0)
    expected_graph.add_edge(1, 2, weight=2.0)

    actual = fnx.edge_current_flow_betweenness_centrality(graph, weight="weight")
    expected = nx.edge_current_flow_betweenness_centrality(expected_graph, weight="weight")
    _assert_mapping_close(actual, expected)


def test_edge_current_flow_betweenness_centrality_directed_error_contract_matches_networkx():
    actual_graph = fnx.DiGraph([(0, 1)])
    expected_graph = nx.DiGraph([(0, 1)])

    with pytest.raises(nx.NetworkXNotImplemented) as expected:
        nx.edge_current_flow_betweenness_centrality(expected_graph)
    with pytest.raises(fnx.NetworkXNotImplemented) as actual:
        fnx.edge_current_flow_betweenness_centrality(actual_graph)

    assert str(actual.value) == str(expected.value)


def test_edge_current_flow_betweenness_centrality_invalid_solver_matches_networkx():
    graph = fnx.path_graph(4)
    expected_graph = nx.path_graph(4)

    with pytest.raises(KeyError) as expected:
        nx.edge_current_flow_betweenness_centrality(expected_graph, solver="bogus")
    with pytest.raises(KeyError) as actual:
        fnx.edge_current_flow_betweenness_centrality(graph, solver="bogus")

    assert actual.value.args == expected.value.args


def test_information_centrality_matches_networkx_without_fallback(monkeypatch):
    graph = fnx.Graph()
    graph.add_edge(0, 1, weight=2.0)
    graph.add_edge(1, 2, weight=3.0)
    graph.add_edge(2, 3, weight=4.0)

    expected_graph = nx.Graph()
    expected_graph.add_edge(0, 1, weight=2.0)
    expected_graph.add_edge(1, 2, weight=3.0)
    expected_graph.add_edge(2, 3, weight=4.0)

    expected = nx.information_centrality(
        expected_graph,
        weight="weight",
        dtype=np.float32,
        solver="cg",
    )

    monkeypatch.setattr(
        nx,
        "information_centrality",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("delegated")),
    )

    actual = fnx.information_centrality(
        graph,
        weight="weight",
        dtype=np.float32,
        solver="cg",
    )
    _assert_mapping_close(actual, expected, tol=1e-6)


def test_information_centrality_error_contract_matches_networkx():
    actual_graph = fnx.path_graph(4)
    expected_graph = nx.path_graph(4)

    with pytest.raises(KeyError) as expected:
        nx.information_centrality(expected_graph, solver="bogus")
    with pytest.raises(KeyError) as actual:
        fnx.information_centrality(actual_graph, solver="bogus")
    assert actual.value.args == expected.value.args

    actual_directed = fnx.DiGraph([(0, 1)])
    expected_directed = nx.DiGraph([(0, 1)])

    with pytest.raises(nx.NetworkXNotImplemented) as expected:
        nx.information_centrality(expected_directed)
    with pytest.raises(fnx.NetworkXNotImplemented) as actual:
        fnx.information_centrality(actual_directed)
    assert str(actual.value) == str(expected.value)


def test_percolation_centrality_honors_attribute_and_states(monkeypatch):
    graph = fnx.path_graph(4)
    for node, value in [(0, 0.1), (1, 0.3), (2, 0.7), (3, 1.0)]:
        graph.nodes[node]["custom_state"] = value

    expected_graph = nx.path_graph(4)
    for node, value in [(0, 0.1), (1, 0.3), (2, 0.7), (3, 1.0)]:
        expected_graph.nodes[node]["custom_state"] = value

    expected_attr = nx.percolation_centrality(expected_graph, attribute="custom_state")
    states = {0: 0.1, 1: 0.3, 2: 0.7, 3: 1.0}
    expected_states = nx.percolation_centrality(expected_graph, states=states)

    def fail(*args, **kwargs):
        raise AssertionError("delegated to networkx.percolation_centrality")

    monkeypatch.setattr(nx, "percolation_centrality", fail)
    actual_attr = fnx.percolation_centrality(graph, attribute="custom_state")
    _assert_mapping_close(actual_attr, expected_attr)

    actual_states = fnx.percolation_centrality(graph, states=states)
    _assert_mapping_close(actual_states, expected_states)
