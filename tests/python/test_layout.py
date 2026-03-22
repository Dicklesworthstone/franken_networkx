"""Tests for drawing layout delegation helpers."""

import networkx as nx
import numpy as np

import franken_networkx as fnx
from franken_networkx.drawing.layout import _to_nx


def _as_tuples(pos):
    return {node: tuple(np.asarray(coords, dtype=float)) for node, coords in pos.items()}


def _assert_positions_close(left, right):
    assert left.keys() == right.keys()
    for node in left:
        assert np.allclose(left[node], right[node])


def test_bfs_layout_matches_networkx():
    graph = fnx.path_graph(5)
    expected = _as_tuples(nx.bfs_layout(nx.path_graph(5), 0))
    actual = _as_tuples(fnx.bfs_layout(graph, 0))
    _assert_positions_close(actual, expected)


def test_bipartite_layout_matches_networkx():
    graph = fnx.complete_bipartite_graph(2, 3)
    expected = _as_tuples(nx.bipartite_layout(_to_nx(graph), nodes=[0, 1]))
    actual = _as_tuples(fnx.bipartite_layout(graph, nodes=[0, 1]))
    _assert_positions_close(actual, expected)


def test_spiral_layout_matches_networkx():
    graph = fnx.path_graph(6)
    expected = _as_tuples(nx.spiral_layout(nx.path_graph(6), resolution=0.2))
    actual = _as_tuples(fnx.spiral_layout(graph, resolution=0.2))
    _assert_positions_close(actual, expected)


def test_multipartite_layout_matches_networkx():
    graph = fnx.Graph()
    graph.add_node("a", subset=0)
    graph.add_node("b", subset=1)
    graph.add_node("c", subset=1)
    graph.add_node("d", subset=2)
    graph.add_edges_from([("a", "b"), ("a", "c"), ("b", "d"), ("c", "d")])

    expected_graph = nx.Graph()
    expected_graph.add_node("a", subset=0)
    expected_graph.add_node("b", subset=1)
    expected_graph.add_node("c", subset=1)
    expected_graph.add_node("d", subset=2)
    expected_graph.add_edges_from([("a", "b"), ("a", "c"), ("b", "d"), ("c", "d")])

    expected = _as_tuples(nx.multipartite_layout(expected_graph))
    actual = _as_tuples(fnx.multipartite_layout(graph))
    _assert_positions_close(actual, expected)


def test_rescale_layout_dict_matches_networkx():
    pos = {"a": np.array([0.0, 0.0]), "b": np.array([2.0, 4.0]), "c": np.array([4.0, 8.0])}
    expected = _as_tuples(nx.rescale_layout_dict(pos, scale=3))
    actual = _as_tuples(fnx.rescale_layout_dict(pos, scale=3))
    _assert_positions_close(actual, expected)


def test_force_directed_layout_exports_are_usable():
    graph = fnx.cycle_graph(5)

    spring = _as_tuples(fnx.fruchterman_reingold_layout(graph, seed=7))
    expected_spring = _as_tuples(nx.fruchterman_reingold_layout(nx.cycle_graph(5), seed=7))
    _assert_positions_close(spring, expected_spring)

    arf = _as_tuples(fnx.arf_layout(graph, seed=7, max_iter=20))
    expected_arf = _as_tuples(nx.arf_layout(nx.cycle_graph(5), seed=7, max_iter=20))
    _assert_positions_close(arf, expected_arf)

    forceatlas = _as_tuples(fnx.forceatlas2_layout(graph, seed=7, max_iter=10))
    expected_forceatlas = _as_tuples(nx.forceatlas2_layout(nx.cycle_graph(5), seed=7, max_iter=10))
    _assert_positions_close(forceatlas, expected_forceatlas)
