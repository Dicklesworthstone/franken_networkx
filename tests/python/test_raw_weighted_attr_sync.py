"""Regression coverage for raw Rust weighted edge-attribute sync."""

import pytest

import franken_networkx as fnx
from franken_networkx import _fnx


def test_raw_weighted_algorithms_see_add_weighted_edges_from_attrs():
    """br-r37-c1-7s20o: raw Rust weighted kernels must not see hop counts."""
    graph = fnx.DiGraph()
    graph.add_weighted_edges_from([(0, 1, 5), (1, 2, 7), (0, 2, 20)])

    assert _fnx.dijkstra_path_length(graph, 0, 2, weight="weight") == pytest.approx(12.0)
    assert _fnx.bellman_ford_path_length(graph, 0, 2, weight="weight") == pytest.approx(12.0)
    assert _fnx.dag_longest_path_length(graph, weight="weight") == pytest.approx(20.0)


def test_raw_weighted_algorithms_see_post_creation_edge_attr_mutation():
    """br-r37-c1-7s20o: raw Rust weighted kernels sync live edge dicts."""
    graph = fnx.DiGraph()
    graph.add_edges_from([(0, 1), (1, 2), (0, 2)])
    graph[0][1]["weight"] = 5
    graph[1][2]["weight"] = 7
    graph[0][2]["weight"] = 20

    assert _fnx.dijkstra_path_length(graph, 0, 2, weight="weight") == pytest.approx(12.0)
    assert _fnx.bellman_ford_path_length(graph, 0, 2, weight="weight") == pytest.approx(12.0)
    assert _fnx.dag_longest_path_length(graph, weight="weight") == pytest.approx(20.0)
