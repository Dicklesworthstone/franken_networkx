"""Tests for community-analysis compatibility wrappers."""

from collections.abc import ValuesView
import networkx as nx
import numpy as np
import pytest
from networkx.algorithms.community import (
    asyn_fluidc as nx_asyn_fluidc,
    kernighan_lin_bisection as nx_kernighan_lin_bisection,
    label_propagation_communities as nx_label_propagation_communities,
)

import franken_networkx as fnx
from franken_networkx.backend import _fnx_to_nx as _to_nx


def _community_frozensets(communities):
    return {frozenset(community) for community in communities}


def _assert_partition_equal(actual, expected):
    assert {frozenset(part) for part in actual} == {frozenset(part) for part in expected}


def test_modularity_matrix_matches_networkx():
    graph = fnx.karate_club_graph()
    nx_graph = _to_nx(graph)

    result = fnx.modularity_matrix(graph)
    expected = nx.modularity_matrix(nx_graph)

    assert result.shape == expected.shape
    assert np.allclose(result, expected)
    assert np.allclose(result.sum(axis=1), 0.0)


def test_modularity_matrix_weight_matches_networkx_without_fallback():
    graph = fnx.Graph()
    graph.add_edge(0, 1, weight=2)
    graph.add_edge(1, 2, weight=3)

    nx_graph = nx.Graph()
    nx_graph.add_edge(0, 1, weight=2)
    nx_graph.add_edge(1, 2, weight=3)

    result = fnx.modularity_matrix(graph, weight="weight")
    expected = nx.modularity_matrix(nx_graph, weight="weight")

    assert result.shape == expected.shape
    assert np.allclose(result, expected)


@pytest.mark.parametrize(
    ("actual_graph", "expected_graph", "expected_error", "actual_error"),
    [
        (fnx.Graph(), nx.Graph(), nx.NetworkXError, fnx.NetworkXError),
        (
            fnx.DiGraph([(0, 1)]),
            nx.DiGraph([(0, 1)]),
            nx.NetworkXNotImplemented,
            fnx.NetworkXNotImplemented,
        ),
        (
            fnx.MultiGraph([(0, 1)]),
            nx.MultiGraph([(0, 1)]),
            nx.NetworkXNotImplemented,
            fnx.NetworkXNotImplemented,
        ),
    ],
)
def test_modularity_matrix_error_contract_matches_networkx(
    actual_graph,
    expected_graph,
    expected_error,
    actual_error,
):
    with pytest.raises(expected_error) as expected:
        nx.modularity_matrix(expected_graph)
    with pytest.raises(actual_error) as actual:
        fnx.modularity_matrix(actual_graph)

    assert str(actual.value) == str(expected.value)


def test_directed_modularity_matrix_matches_networkx():
    base = fnx.karate_club_graph()
    graph = fnx.DiGraph(base)
    nx_graph = _to_nx(graph)

    result = fnx.directed_modularity_matrix(graph)
    expected = nx.directed_modularity_matrix(nx_graph)

    assert result.shape == expected.shape
    assert np.allclose(result, expected)


def test_modularity_spectrum_matches_networkx():
    graph = fnx.karate_club_graph()
    nx_graph = _to_nx(graph)

    result = fnx.modularity_spectrum(graph)
    expected = nx.modularity_spectrum(nx_graph)

    assert len(result) == len(expected)
    assert np.allclose(result, expected)


def test_label_propagation_communities_matches_networkx():
    graph = fnx.path_graph(6)
    nx_graph = _to_nx(graph)

    result = fnx.label_propagation_communities(graph)
    expected = nx_label_propagation_communities(nx_graph)

    assert isinstance(result, ValuesView)
    assert _community_frozensets(result) == _community_frozensets(expected)
    assert all(isinstance(community, set) for community in result)


def test_label_propagation_communities_multigraph_matches_networkx():
    graph = fnx.MultiGraph()
    graph.add_edge(0, 1)
    graph.add_edge(0, 1)
    graph.add_edge(1, 2)
    nx_graph = _to_nx(graph)

    result = fnx.label_propagation_communities(graph)
    expected = nx_label_propagation_communities(nx_graph)

    assert _community_frozensets(result) == _community_frozensets(expected)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"seed": 7},
        {"seed": 7, "resolution": 0.5},
        {"seed": 7, "resolution": 0.5, "threshold": 0.1},
        {"seed": 7, "resolution": 0.5, "max_level": 1},
    ],
)
def test_louvain_communities_matches_networkx_for_multilevel_controls(kwargs):
    graph = fnx.barbell_graph(4, 2)
    nx_graph = _to_nx(graph)

    result = fnx.louvain_communities(graph, **kwargs)
    expected = nx.community.louvain_communities(nx_graph, **kwargs)

    _assert_partition_equal(result, expected)


def test_louvain_communities_max_level_error_contract_matches_networkx():
    graph = fnx.path_graph(4)
    nx_graph = _to_nx(graph)

    with pytest.raises(ValueError) as expected:
        nx.community.louvain_communities(nx_graph, max_level=0)
    with pytest.raises(ValueError) as actual:
        fnx.louvain_communities(graph, max_level=0)

    assert str(actual.value) == str(expected.value)


@pytest.mark.parametrize(
    ("actual_graph", "expected_graph", "expected_error", "actual_error"),
    [
        (
            fnx.DiGraph([(0, 1)]),
            nx.DiGraph([(0, 1)]),
            nx.NetworkXNotImplemented,
            fnx.NetworkXNotImplemented,
        ),
        (
            fnx.MultiDiGraph([(0, 1)]),
            nx.MultiDiGraph([(0, 1)]),
            nx.NetworkXNotImplemented,
            fnx.NetworkXNotImplemented,
        ),
    ],
)
def test_label_propagation_communities_directed_error_contract_matches_networkx(
    actual_graph,
    expected_graph,
    expected_error,
    actual_error,
):
    with pytest.raises(expected_error) as expected:
        list(nx_label_propagation_communities(expected_graph))
    with pytest.raises(actual_error) as actual:
        list(fnx.label_propagation_communities(actual_graph))

    assert str(actual.value) == str(expected.value)


@pytest.mark.parametrize("graph_constructor", (fnx.DiGraph, fnx.MultiGraph))
def test_asyn_fluidc_rejects_directed_and_multigraph(graph_constructor):
    actual_graph = graph_constructor([(0, 1), (1, 2)])
    expected_graph = nx.DiGraph([(0, 1), (1, 2)]) if graph_constructor is fnx.DiGraph else nx.MultiGraph([(0, 1), (1, 2)])

    with pytest.raises(nx.NetworkXNotImplemented) as expected:
        list(nx_asyn_fluidc(expected_graph, 1))
    with pytest.raises(fnx.NetworkXNotImplemented) as actual:
        list(fnx.asyn_fluidc(actual_graph, 1))

    assert str(actual.value) == str(expected.value)


def test_asyn_fluidc_error_contract_matches_networkx():
    actual_graph = fnx.Graph()
    expected_graph = nx.Graph()
    actual_graph.add_node("a")
    expected_graph.add_node("a")

    for k in ("hi", -1, 3):
        with pytest.raises(nx.NetworkXError) as expected:
            list(nx_asyn_fluidc(expected_graph, k))
        with pytest.raises(fnx.NetworkXError) as actual:
            list(fnx.asyn_fluidc(actual_graph, k))
        assert str(actual.value) == str(expected.value)

    with pytest.raises(ValueError) as expected:
        list(nx_asyn_fluidc(expected_graph, 1, max_iter=0))
    with pytest.raises(ValueError) as actual:
        list(fnx.asyn_fluidc(actual_graph, 1, max_iter=0))
    assert str(actual.value) == str(expected.value)

    actual_graph.add_node("b")
    expected_graph.add_node("b")
    with pytest.raises(nx.NetworkXError) as expected:
        list(nx_asyn_fluidc(expected_graph, 1))
    with pytest.raises(fnx.NetworkXError) as actual:
        list(fnx.asyn_fluidc(actual_graph, 1))
    assert str(actual.value) == str(expected.value)


def test_asyn_fluidc_seeded_cases_match_networkx():
    single_actual = fnx.Graph()
    single_actual.add_node("a")
    single_expected = nx.Graph()
    single_expected.add_node("a")
    assert _community_frozensets(fnx.asyn_fluidc(single_actual, 1)) == _community_frozensets(
        nx_asyn_fluidc(single_expected, 1),
    )

    two_actual = fnx.Graph()
    two_actual.add_edge("a", "b")
    two_expected = nx.Graph()
    two_expected.add_edge("a", "b")
    assert _community_frozensets(fnx.asyn_fluidc(two_actual, 2)) == _community_frozensets(
        nx_asyn_fluidc(two_expected, 2),
    )

    graph = fnx.Graph()
    graph.add_edges_from(
        [
            ("a", "b"),
            ("a", "c"),
            ("b", "c"),
            ("c", "d"),
            ("d", "e"),
            ("d", "f"),
            ("f", "e"),
        ],
    )
    expected_graph = nx.Graph()
    expected_graph.add_edges_from(
        [
            ("a", "b"),
            ("a", "c"),
            ("b", "c"),
            ("c", "d"),
            ("d", "e"),
            ("d", "f"),
            ("f", "e"),
        ],
    )
    assert _community_frozensets(fnx.asyn_fluidc(graph, 2, seed=7)) == _community_frozensets(
        nx_asyn_fluidc(expected_graph, 2, seed=7),
    )


def test_kernighan_lin_bisection_matches_networkx():
    graph = fnx.barbell_graph(3, 0)
    expected_graph = nx.barbell_graph(3, 0)

    actual = fnx.kernighan_lin_bisection(graph, seed=1)
    expected = nx_kernighan_lin_bisection(expected_graph, seed=1)

    _assert_partition_equal(actual, expected)


def test_kernighan_lin_bisection_partition_and_multigraph_match_networkx():
    graph = fnx.Graph()
    graph.add_edges_from([("A", "B"), ("A", "C"), ("B", "C"), ("C", "D")])
    expected_graph = nx.Graph()
    expected_graph.add_edges_from([("A", "B"), ("A", "C"), ("B", "C"), ("C", "D")])
    partition = ({"A", "B"}, {"C", "D"})

    actual = fnx.kernighan_lin_bisection(graph, partition=partition)
    expected = nx_kernighan_lin_bisection(expected_graph, partition=partition)
    _assert_partition_equal(actual, expected)

    multigraph = fnx.MultiGraph()
    multigraph.add_edges_from([(0, 1), (1, 2), (2, 3), (3, 0)])
    multigraph.add_edges_from([(0, 1), (1, 2), (2, 3), (3, 0)])
    multigraph.remove_edge(1, 2)

    expected_multigraph = nx.MultiGraph()
    expected_multigraph.add_edges_from([(0, 1), (1, 2), (2, 3), (3, 0)])
    expected_multigraph.add_edges_from([(0, 1), (1, 2), (2, 3), (3, 0)])
    expected_multigraph.remove_edge(1, 2)

    actual_multigraph = fnx.kernighan_lin_bisection(multigraph, seed=0)
    expected_multigraph_partition = nx_kernighan_lin_bisection(expected_multigraph, seed=0)
    _assert_partition_equal(actual_multigraph, expected_multigraph_partition)


def test_kernighan_lin_bisection_weight_and_error_contract_match_networkx():
    graph = fnx.cycle_graph(4)
    expected_graph = nx.cycle_graph(4)

    def my_weight(u, v, d):
        if u == 2 and v == 3:
            return None
        return u + v

    actual = fnx.kernighan_lin_bisection(graph, weight=my_weight)
    expected = nx_kernighan_lin_bisection(expected_graph, weight=my_weight)
    _assert_partition_equal(actual, expected)

    actual_directed = fnx.DiGraph([(0, 1)])
    expected_directed = nx.DiGraph([(0, 1)])
    with pytest.raises(nx.NetworkXNotImplemented) as expected_directed_error:
        nx_kernighan_lin_bisection(expected_directed)
    with pytest.raises(fnx.NetworkXNotImplemented) as actual_directed_error:
        fnx.kernighan_lin_bisection(actual_directed)
    assert str(actual_directed_error.value) == str(expected_directed_error.value)

    invalid_partition = ({0, 1}, {1, 2, 3})
    actual_graph = fnx.path_graph(4)
    expected_invalid_graph = nx.path_graph(4)
    with pytest.raises(nx.NetworkXError) as expected_invalid_error:
        nx_kernighan_lin_bisection(expected_invalid_graph, partition=invalid_partition)
    with pytest.raises(fnx.NetworkXError) as actual_invalid_error:
        fnx.kernighan_lin_bisection(actual_graph, partition=invalid_partition)
    assert str(actual_invalid_error.value) == str(expected_invalid_error.value)

    too_many_blocks = ({0}, {1}, {2, 3})
    with pytest.raises(nx.NetworkXError) as expected_block_error:
        nx_kernighan_lin_bisection(expected_invalid_graph, partition=too_many_blocks)
    with pytest.raises(fnx.NetworkXError) as actual_block_error:
        fnx.kernighan_lin_bisection(actual_graph, partition=too_many_blocks)
    assert str(actual_block_error.value) == str(expected_block_error.value)


def test_within_inter_cluster_matches_networkx():
    graph = fnx.Graph()
    graph.add_edges_from([("a", "b"), ("b", "c"), ("c", "d"), ("a", "d")])
    for node in ("a", "b"):
        graph.nodes[node]["community"] = 0
    for node in ("c", "d"):
        graph.nodes[node]["community"] = 1

    result = list(fnx.within_inter_cluster(graph, ebunch=[("a", "c"), ("b", "d")]))

    nx_graph = nx.Graph()
    nx_graph.add_edges_from([("a", "b"), ("b", "c"), ("c", "d"), ("a", "d")])
    for node in ("a", "b"):
        nx_graph.nodes[node]["community"] = 0
    for node in ("c", "d"):
        nx_graph.nodes[node]["community"] = 1
    expected = list(nx.within_inter_cluster(nx_graph, ebunch=[("a", "c"), ("b", "d")]))

    assert result == expected


def test_prominent_group_matches_networkx_when_pandas_available():
    pytest.importorskip("pandas")

    graph = fnx.karate_club_graph()
    result = fnx.prominent_group(graph, 3)
    expected = nx.prominent_group(nx.karate_club_graph(), 3)

    assert result == expected
