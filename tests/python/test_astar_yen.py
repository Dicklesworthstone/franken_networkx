"""Tests for A* shortest path and Yen's K-shortest simple paths."""

import re

import networkx as nx
import pytest

import franken_networkx as fnx


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def weighted_triangle():
    """Triangle with unequal weights: direct 0->2 is expensive."""
    G = fnx.Graph()
    G.add_edge(0, 1, weight=1.0)
    G.add_edge(1, 2, weight=1.0)
    G.add_edge(0, 2, weight=5.0)
    return G


@pytest.fixture
def diamond():
    """Diamond: 0--1--3, 0--2--3, with weights."""
    G = fnx.Graph()
    G.add_edge(0, 1, weight=1.0)
    G.add_edge(0, 2, weight=2.0)
    G.add_edge(1, 3, weight=1.0)
    G.add_edge(2, 3, weight=1.0)
    return G


@pytest.fixture
def path5():
    G = fnx.Graph()
    for i in range(4):
        G.add_edge(i, i + 1, weight=1.0)
    return G


# ---------------------------------------------------------------------------
# astar_path
# ---------------------------------------------------------------------------


class TestAstarPath:
    def test_basic(self, weighted_triangle):
        path = fnx.astar_path(weighted_triangle, 0, 2)
        assert path == [0, 1, 2]

    def test_same_node(self):
        G = fnx.Graph()
        G.add_node(0)
        path = fnx.astar_path(G, 0, 0)
        assert path == [0]

    def test_no_path_raises(self):
        G = fnx.Graph()
        G.add_node(0)
        G.add_node(1)
        with pytest.raises(ValueError):
            fnx.astar_path(G, 0, 1)

    def test_with_zero_heuristic(self, weighted_triangle):
        path = fnx.astar_path(weighted_triangle, 0, 2, heuristic=lambda u, v: 0)
        assert path == [0, 1, 2]

    def test_diamond(self, diamond):
        path = fnx.astar_path(diamond, 0, 3)
        # 0->1->3 has total weight 2, 0->2->3 has total weight 3.
        assert path == [0, 1, 3]

    def test_path5(self, path5):
        path = fnx.astar_path(path5, 0, 4)
        assert path == [0, 1, 2, 3, 4]

    def test_string_nodes(self):
        G = fnx.Graph()
        G.add_edge("a", "b", weight=1.0)
        G.add_edge("b", "c", weight=1.0)
        path = fnx.astar_path(G, "a", "c")
        assert path == ["a", "b", "c"]

    def test_heuristic_exception_matches_networkx(self):
        G_fnx = fnx.path_graph(3)
        G_nx = nx.path_graph(3)

        def heuristic(u, v):
            raise RuntimeError("boom")

        with pytest.raises(RuntimeError) as expected:
            nx.astar_path(G_nx, 0, 2, heuristic=heuristic)

        with pytest.raises(type(expected.value), match=re.escape(str(expected.value))):
            fnx.astar_path(G_fnx, 0, 2, heuristic=heuristic)


# ---------------------------------------------------------------------------
# astar_path_length
# ---------------------------------------------------------------------------


class TestAstarPathLength:
    def test_basic(self, weighted_triangle):
        length = fnx.astar_path_length(weighted_triangle, 0, 2)
        assert abs(length - 2.0) < 1e-9

    def test_same_node(self):
        G = fnx.Graph()
        G.add_node(0)
        length = fnx.astar_path_length(G, 0, 0)
        assert abs(length - 0.0) < 1e-9

    def test_no_path_raises(self):
        G = fnx.Graph()
        G.add_node(0)
        G.add_node(1)
        with pytest.raises(ValueError):
            fnx.astar_path_length(G, 0, 1)

    def test_diamond(self, diamond):
        length = fnx.astar_path_length(diamond, 0, 3)
        assert abs(length - 2.0) < 1e-9

    def test_unit_weights(self, path5):
        length = fnx.astar_path_length(path5, 0, 4)
        assert abs(length - 4.0) < 1e-9

    def test_heuristic_exception_matches_networkx(self):
        G_fnx = fnx.path_graph(3)
        G_nx = nx.path_graph(3)

        def heuristic(u, v):
            raise RuntimeError("boom")

        with pytest.raises(RuntimeError) as expected:
            nx.astar_path_length(G_nx, 0, 2, heuristic=heuristic)

        with pytest.raises(type(expected.value), match=re.escape(str(expected.value))):
            fnx.astar_path_length(G_fnx, 0, 2, heuristic=heuristic)


# ---------------------------------------------------------------------------
# shortest_simple_paths
# ---------------------------------------------------------------------------


class TestShortestSimplePaths:
    def test_unweighted_order(self, weighted_triangle):
        # Unweighted: direct edge 0->2 (1 hop) < 0->1->2 (2 hops).
        paths = fnx.shortest_simple_paths(weighted_triangle, 0, 2)
        assert len(paths) == 2
        assert paths[0] == [0, 2]
        assert paths[1] == [0, 1, 2]

    def test_weighted_order(self, weighted_triangle):
        # Weighted: 0->1->2 (weight 2) < 0->2 (weight 5).
        paths = fnx.shortest_simple_paths(weighted_triangle, 0, 2, weight="weight")
        assert len(paths) == 2
        assert paths[0] == [0, 1, 2]
        assert paths[1] == [0, 2]

    def test_diamond(self, diamond):
        paths = fnx.shortest_simple_paths(diamond, 0, 3, weight="weight")
        assert len(paths) == 2
        # 0->1->3 (weight 2) before 0->2->3 (weight 3).
        assert paths[0] == [0, 1, 3]
        assert paths[1] == [0, 2, 3]

    def test_no_path(self):
        G = fnx.Graph()
        G.add_node(0)
        G.add_node(1)
        paths = fnx.shortest_simple_paths(G, 0, 1)
        assert paths == []

    def test_same_node(self):
        G = fnx.Graph()
        G.add_node(0)
        paths = fnx.shortest_simple_paths(G, 0, 0)
        # Single node path
        assert len(paths) >= 1
        assert paths[0] == [0]

    def test_path5_all_paths(self, path5):
        # In a simple path graph there's only one path from 0 to 4.
        paths = fnx.shortest_simple_paths(path5, 0, 4)
        assert len(paths) == 1
        assert paths[0] == [0, 1, 2, 3, 4]

    def test_multiple_paths(self):
        """Graph with multiple alternative paths."""
        G = fnx.Graph()
        G.add_edge(0, 1)
        G.add_edge(0, 2)
        G.add_edge(1, 3)
        G.add_edge(2, 3)
        G.add_edge(1, 2)
        paths = fnx.shortest_simple_paths(G, 0, 3)
        # Should find multiple paths of varying lengths.
        assert len(paths) >= 2
        # All paths must start at 0 and end at 3.
        for path in paths:
            assert path[0] == 0
            assert path[-1] == 3
