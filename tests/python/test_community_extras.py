"""Tests for community-analysis compatibility wrappers."""

from collections.abc import ValuesView
import networkx as nx
import numpy as np
import pytest
from networkx.algorithms.community import (
    label_propagation_communities as nx_label_propagation_communities,
)

import franken_networkx as fnx
from franken_networkx.backend import _fnx_to_nx as _to_nx


def _community_frozensets(communities):
    return {frozenset(community) for community in communities}


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
