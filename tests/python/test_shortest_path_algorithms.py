"""Comprehensive tests for shortest path algorithm bindings.

Tests cover:
- dijkstra_path_length
- bellman_ford_path_length
- single_source_dijkstra / _path / _path_length
- single_source_bellman_ford / _path / _path_length
- single_target_shortest_path / _length
- all_pairs_dijkstra_path / _path_length
- all_pairs_bellman_ford_path / _path_length
- floyd_warshall / floyd_warshall_predecessor_and_distance
- bidirectional_shortest_path
- negative_edge_cycle
- predecessor
- path_weight
"""

import math
import pytest
import franken_networkx as fnx
import networkx as nx


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def weighted_triangle():
    """Triangle a-b-c with weights: a-b=2, b-c=3, a-c=10."""
    g = fnx.Graph()
    g.add_edge("a", "b", weight=2.0)
    g.add_edge("b", "c", weight=3.0)
    g.add_edge("a", "c", weight=10.0)
    return g


@pytest.fixture
def path_graph():
    """Simple unweighted path: a - b - c - d."""
    g = fnx.Graph()
    g.add_edge("a", "b")
    g.add_edge("b", "c")
    g.add_edge("c", "d")
    return g


@pytest.fixture
def disconnected_graph():
    """Two disconnected nodes."""
    g = fnx.Graph()
    g.add_node("a")
    g.add_node("b")
    return g


def _bellman_ford_directed_graph_pair():
    g_fnx = fnx.DiGraph()
    g_nx = nx.DiGraph()
    for graph in (g_fnx, g_nx):
        graph.add_edge("a", "b", weight=1.0)
        graph.add_edge("b", "c", weight=2.0)
        graph.add_edge("c", "a", weight=4.0)
        graph.add_edge("a", "c", weight=5.0)
        graph.add_edge("c", "b", weight=1.0)
        graph.add_edge("b", "a", weight=3.0)
    return g_fnx, g_nx


def _dijkstra_directed_graph_pair():
    g_fnx = fnx.DiGraph()
    g_nx = nx.DiGraph()
    for graph in (g_fnx, g_nx):
        graph.add_edge("a", "b", weight=1.0)
        graph.add_edge("b", "c", weight=2.0)
        graph.add_edge("a", "c", weight=10.0)
    return g_fnx, g_nx


def _single_target_directed_graph_pair():
    g_fnx = fnx.DiGraph()
    g_nx = nx.DiGraph()
    for graph in (g_fnx, g_nx):
        graph.add_edge("a", "c")
        graph.add_edge("b", "c")
        graph.add_edge("a", "b")
        graph.add_edge("b", "d")
        graph.add_edge("d", "c")
    return g_fnx, g_nx


# ---------------------------------------------------------------------------
# dijkstra_path_length
# ---------------------------------------------------------------------------

class TestDijkstraPathLength:
    def test_direct_edge(self, weighted_triangle):
        # a->c direct is 10, but a->b->c is 5
        assert fnx.dijkstra_path_length(weighted_triangle, "a", "c", weight="weight") == 5.0

    def test_same_node(self, weighted_triangle):
        assert fnx.dijkstra_path_length(weighted_triangle, "a", "a", weight="weight") == 0.0

    def test_no_path(self, disconnected_graph):
        with pytest.raises(fnx.NetworkXNoPath):
            fnx.dijkstra_path_length(disconnected_graph, "a", "b", weight="weight")

    def test_unit_weight(self, path_graph):
        assert fnx.dijkstra_path_length(path_graph, "a", "d", weight="weight") == 3.0


# ---------------------------------------------------------------------------
# bellman_ford_path_length
# ---------------------------------------------------------------------------

class TestBellmanFordPathLength:
    def test_simple(self, path_graph):
        assert fnx.bellman_ford_path_length(path_graph, "a", "c", weight="weight") == 2.0

    def test_weighted(self, weighted_triangle):
        assert fnx.bellman_ford_path_length(weighted_triangle, "a", "c", weight="weight") == 5.0

    def test_no_path(self, disconnected_graph):
        with pytest.raises(fnx.NetworkXNoPath):
            fnx.bellman_ford_path_length(disconnected_graph, "a", "b", weight="weight")

    def test_directed_reverse_path_missing(self):
        g = fnx.DiGraph()
        g.add_edge("a", "b", weight=1.0)

        with pytest.raises(fnx.NetworkXNoPath):
            fnx.dijkstra_path_length(g, "b", "a", weight="weight")

        with pytest.raises(fnx.NetworkXNoPath):
            fnx.bellman_ford_path_length(g, "b", "a", weight="weight")


# ---------------------------------------------------------------------------
# single_source_dijkstra
# ---------------------------------------------------------------------------

class TestSingleSourceDijkstra:
    def test_returns_tuple(self, weighted_triangle):
        dists, paths = fnx.single_source_dijkstra(weighted_triangle, "a", weight="weight")
        assert dists["a"] == 0.0
        assert dists["b"] == 2.0
        assert dists["c"] == 5.0
        assert paths["a"] == ["a"]
        assert paths["b"] == ["a", "b"]
        assert paths["c"] == ["a", "b", "c"]

    def test_single_node(self):
        g = fnx.Graph()
        g.add_node("x")
        dists, paths = fnx.single_source_dijkstra(g, "x", weight="weight")
        assert dists == {"x": 0.0}
        assert paths == {"x": ["x"]}

    def test_directed_matches_networkx(self):
        g_fnx, g_nx = _dijkstra_directed_graph_pair()
        assert fnx.single_source_dijkstra(
            g_fnx, "a", weight="weight"
        ) == nx.single_source_dijkstra(g_nx, "a", weight="weight")


class TestDirectedMultiSourceDijkstra:
    def test_only_reaches_successors(self):
        g = fnx.DiGraph()
        g.add_edge("a", "b", weight=1.0)
        g.add_edge("b", "c", weight=2.0)

        dists, paths = fnx.multi_source_dijkstra(g, ["b"], weight="weight")
        assert dists["b"] == 0.0
        assert dists["c"] == 2.0
        assert "a" not in dists
        assert paths["c"] == ["b", "c"]


# ---------------------------------------------------------------------------
# single_source_dijkstra_path
# ---------------------------------------------------------------------------

class TestSingleSourceDijkstraPath:
    def test_paths(self, weighted_triangle):
        paths = fnx.single_source_dijkstra_path(weighted_triangle, "a", weight="weight")
        assert paths["c"] == ["a", "b", "c"]

    def test_single_node(self):
        g = fnx.Graph()
        g.add_node("x")
        paths = fnx.single_source_dijkstra_path(g, "x", weight="weight")
        assert paths == {"x": ["x"]}

    def test_directed_matches_networkx(self):
        g_fnx, g_nx = _dijkstra_directed_graph_pair()
        assert fnx.single_source_dijkstra_path(
            g_fnx, "a", weight="weight"
        ) == nx.single_source_dijkstra_path(g_nx, "a", weight="weight")


# ---------------------------------------------------------------------------
# single_source_dijkstra_path_length
# ---------------------------------------------------------------------------

class TestSingleSourceDijkstraPathLength:
    def test_distances(self, weighted_triangle):
        dists = fnx.single_source_dijkstra_path_length(weighted_triangle, "a", weight="weight")
        assert dists["a"] == 0.0
        assert dists["b"] == 2.0
        assert dists["c"] == 5.0

    def test_directed_matches_networkx(self):
        g_fnx, g_nx = _dijkstra_directed_graph_pair()
        assert fnx.single_source_dijkstra_path_length(
            g_fnx, "a", weight="weight"
        ) == nx.single_source_dijkstra_path_length(g_nx, "a", weight="weight")


# ---------------------------------------------------------------------------
# single_source_bellman_ford
# ---------------------------------------------------------------------------

class TestSingleSourceBellmanFord:
    def test_returns_tuple(self, path_graph):
        dists, paths = fnx.single_source_bellman_ford(path_graph, "a", weight="weight")
        assert dists["a"] == 0.0
        assert dists["d"] == 3.0
        assert paths["d"] == ["a", "b", "c", "d"]

    def test_weighted(self, weighted_triangle):
        dists, paths = fnx.single_source_bellman_ford(weighted_triangle, "a", weight="weight")
        assert dists["c"] == 5.0
        assert paths["c"] == ["a", "b", "c"]

    def test_directed_matches_networkx(self):
        g_fnx, g_nx = _bellman_ford_directed_graph_pair()
        assert fnx.single_source_bellman_ford(
            g_fnx, "a", weight="weight"
        ) == nx.single_source_bellman_ford(g_nx, "a", weight="weight")


# ---------------------------------------------------------------------------
# single_source_bellman_ford_path
# ---------------------------------------------------------------------------

class TestSingleSourceBellmanFordPath:
    def test_paths(self, path_graph):
        paths = fnx.single_source_bellman_ford_path(path_graph, "a", weight="weight")
        assert paths["c"] == ["a", "b", "c"]

    def test_directed_matches_networkx(self):
        g_fnx, g_nx = _bellman_ford_directed_graph_pair()
        assert fnx.single_source_bellman_ford_path(
            g_fnx, "a", weight="weight"
        ) == nx.single_source_bellman_ford_path(g_nx, "a", weight="weight")


# ---------------------------------------------------------------------------
# single_source_bellman_ford_path_length
# ---------------------------------------------------------------------------

class TestSingleSourceBellmanFordPathLength:
    def test_distances(self, path_graph):
        dists = fnx.single_source_bellman_ford_path_length(path_graph, "a", weight="weight")
        assert dists["a"] == 0.0
        assert dists["d"] == 3.0

    def test_directed_matches_networkx(self):
        g_fnx, g_nx = _bellman_ford_directed_graph_pair()
        assert fnx.single_source_bellman_ford_path_length(
            g_fnx, "a", weight="weight"
        ) == nx.single_source_bellman_ford_path_length(g_nx, "a", weight="weight")


# ---------------------------------------------------------------------------
# single_target_shortest_path
# ---------------------------------------------------------------------------

class TestSingleTargetShortestPath:
    def test_paths_end_at_target(self, path_graph):
        paths = fnx.single_target_shortest_path(path_graph, "d")
        for node, path in paths.items():
            assert path[0] == node
            assert path[-1] == "d"

    def test_lengths(self, path_graph):
        paths = fnx.single_target_shortest_path(path_graph, "d")
        assert len(paths["a"]) == 4  # a -> b -> c -> d
        assert len(paths["d"]) == 1  # d

    def test_with_cutoff(self, path_graph):
        paths = fnx.single_target_shortest_path(path_graph, "d", cutoff=1)
        assert "c" in paths
        assert "a" not in paths  # a is 3 hops away

    def test_directed_matches_networkx(self):
        g_fnx, g_nx = _single_target_directed_graph_pair()
        assert fnx.single_target_shortest_path(
            g_fnx, "c"
        ) == nx.single_target_shortest_path(g_nx, "c")


# ---------------------------------------------------------------------------
# single_target_shortest_path_length
# ---------------------------------------------------------------------------

class TestSingleTargetShortestPathLength:
    def test_lengths(self, path_graph):
        lengths = fnx.single_target_shortest_path_length(path_graph, "d")
        assert lengths["d"] == 0
        assert lengths["c"] == 1
        assert lengths["a"] == 3

    def test_weighted_via_shortest_path_length_undirected(self, weighted_triangle):
        lengths = fnx.shortest_path_length(weighted_triangle, target="c", weight="weight")
        assert lengths["c"] == 0.0
        assert lengths["b"] == 3.0
        assert lengths["a"] == 5.0

    def test_weighted_via_shortest_path_length_directed(self):
        g = fnx.DiGraph()
        g.add_edge("a", "b", weight=2.0)
        g.add_edge("b", "c", weight=3.0)
        lengths = fnx.shortest_path_length(g, target="c", weight="weight")
        assert lengths["c"] == 0.0
        assert lengths["b"] == 3.0
        assert lengths["a"] == 5.0

    def test_directed_matches_networkx(self):
        g_fnx, g_nx = _single_target_directed_graph_pair()
        assert fnx.single_target_shortest_path_length(
            g_fnx, "c"
        ) == nx.single_target_shortest_path_length(g_nx, "c")


# ---------------------------------------------------------------------------
# all_pairs_dijkstra_path
# ---------------------------------------------------------------------------

class TestAllPairsDijkstraPath:
    def test_all_pairs(self, weighted_triangle):
        paths = dict(fnx.all_pairs_dijkstra_path(weighted_triangle, weight="weight"))
        assert paths["a"]["c"] == ["a", "b", "c"]
        assert paths["c"]["a"] == ["c", "b", "a"]

    def test_symmetric(self, path_graph):
        paths = dict(fnx.all_pairs_dijkstra_path(path_graph, weight="weight"))
        assert len(paths["a"]["d"]) == len(paths["d"]["a"])


# ---------------------------------------------------------------------------
# all_pairs_dijkstra_path_length
# ---------------------------------------------------------------------------

class TestAllPairsDijkstraPathLength:
    def test_distances(self, weighted_triangle):
        dists = dict(fnx.all_pairs_dijkstra_path_length(weighted_triangle, weight="weight"))
        assert dists["a"]["c"] == 5.0
        assert dists["a"]["a"] == 0.0

    def test_symmetric(self, path_graph):
        dists = dict(fnx.all_pairs_dijkstra_path_length(path_graph, weight="weight"))
        assert dists["a"]["d"] == dists["d"]["a"]

    def test_directed_distances(self):
        g_fnx = fnx.DiGraph()
        g_nx = nx.DiGraph()
        for graph in (g_fnx, g_nx):
            graph.add_edge("a", "b", weight=1.0)
            graph.add_edge("b", "c", weight=2.0)
            graph.add_edge("a", "c", weight=10.0)

        assert dict(fnx.all_pairs_dijkstra_path_length(
            g_fnx, weight="weight"
        )) == dict(nx.all_pairs_dijkstra_path_length(g_nx, weight="weight"))


# ---------------------------------------------------------------------------
# all_pairs_bellman_ford_path
# ---------------------------------------------------------------------------

class TestAllPairsBellmanFordPath:
    def test_all_pairs(self, path_graph):
        paths = dict(fnx.all_pairs_bellman_ford_path(path_graph, weight="weight"))
        assert paths["a"]["d"] == ["a", "b", "c", "d"]

    def test_directed_matches_networkx(self):
        g_fnx, g_nx = _bellman_ford_directed_graph_pair()
        assert dict(fnx.all_pairs_bellman_ford_path(
            g_fnx, weight="weight"
        )) == dict(nx.all_pairs_bellman_ford_path(g_nx, weight="weight"))


# ---------------------------------------------------------------------------
# all_pairs_bellman_ford_path_length
# ---------------------------------------------------------------------------

class TestAllPairsBellmanFordPathLength:
    def test_distances(self, path_graph):
        dists = dict(fnx.all_pairs_bellman_ford_path_length(path_graph, weight="weight"))
        assert dists["a"]["d"] == 3.0

    def test_directed_matches_networkx(self):
        g_fnx, g_nx = _bellman_ford_directed_graph_pair()
        assert dict(fnx.all_pairs_bellman_ford_path_length(
            g_fnx, weight="weight"
        )) == dict(nx.all_pairs_bellman_ford_path_length(g_nx, weight="weight"))


# ---------------------------------------------------------------------------
# floyd_warshall
# ---------------------------------------------------------------------------

class TestFloydWarshall:
    def test_simple(self, path_graph):
        dists = fnx.floyd_warshall(path_graph, weight="weight")
        assert dists["a"]["d"] == 3.0
        assert dists["a"]["a"] == 0.0

    def test_weighted(self, weighted_triangle):
        dists = fnx.floyd_warshall(weighted_triangle, weight="weight")
        assert dists["a"]["c"] == 5.0  # a->b->c, not a->c=10

    def test_disconnected(self, disconnected_graph):
        dists = fnx.floyd_warshall(disconnected_graph, weight="weight")
        assert dists["a"]["b"] == math.inf

    def test_symmetric(self, path_graph):
        dists = fnx.floyd_warshall(path_graph, weight="weight")
        for u in dists:
            for v in dists[u]:
                assert dists[u][v] == dists[v][u]


# ---------------------------------------------------------------------------
# floyd_warshall_predecessor_and_distance
# ---------------------------------------------------------------------------

class TestFloydWarshallPredecessorAndDistance:
    def test_returns_tuple(self, path_graph):
        preds, dists = fnx.floyd_warshall_predecessor_and_distance(path_graph, weight="weight")
        assert isinstance(preds, dict)
        assert isinstance(dists, dict)
        assert dists["a"]["d"] == 3.0

    def test_predecessors_exist(self, weighted_triangle):
        preds, dists = fnx.floyd_warshall_predecessor_and_distance(weighted_triangle, weight="weight")
        assert preds["a"]["b"] == "a"
        assert preds["a"]["c"] == "b"

    def test_matches_networkx_on_tied_paths(self):
        g_fnx = fnx.Graph()
        g_nx = nx.Graph()
        for graph in (g_fnx, g_nx):
            graph.add_edge("a", "b", weight=1.0)
            graph.add_edge("a", "c", weight=1.0)
            graph.add_edge("b", "d", weight=1.0)
            graph.add_edge("c", "d", weight=1.0)

        fnx_preds, fnx_dists = fnx.floyd_warshall_predecessor_and_distance(g_fnx, weight="weight")
        nx_preds, nx_dists = nx.floyd_warshall_predecessor_and_distance(g_nx, weight="weight")
        assert fnx_preds == nx_preds
        assert fnx_dists == nx_dists


# ---------------------------------------------------------------------------
# bidirectional_shortest_path
# ---------------------------------------------------------------------------

class TestBidirectionalShortestPath:
    def test_simple(self, path_graph):
        path = fnx.bidirectional_shortest_path(path_graph, "a", "d")
        assert path[0] == "a"
        assert path[-1] == "d"
        assert len(path) == 4

    def test_same_node(self, path_graph):
        path = fnx.bidirectional_shortest_path(path_graph, "a", "a")
        assert path == ["a"]

    def test_no_path(self, disconnected_graph):
        with pytest.raises(fnx.NetworkXNoPath):
            fnx.bidirectional_shortest_path(disconnected_graph, "a", "b")

    def test_optimal(self, weighted_triangle):
        # Unweighted: a-c is 1 hop (direct edge exists)
        path = fnx.bidirectional_shortest_path(weighted_triangle, "a", "c")
        assert len(path) == 2  # direct path


# ---------------------------------------------------------------------------
# negative_edge_cycle
# ---------------------------------------------------------------------------

class TestNegativeEdgeCycle:
    def test_no_cycle(self, path_graph):
        assert fnx.negative_edge_cycle(path_graph, weight="weight") is False

    def test_positive_cycle(self):
        g = fnx.Graph()
        g.add_edge("a", "b", weight=1.0)
        g.add_edge("b", "c", weight=2.0)
        g.add_edge("c", "a", weight=3.0)
        assert fnx.negative_edge_cycle(g, weight="weight") is False

    def test_negative_cycle(self):
        g = fnx.Graph()
        g.add_edge("a", "b", weight=-2.0)
        g.add_edge("b", "c", weight=-3.0)
        g.add_edge("c", "a", weight=-1.0)
        assert fnx.negative_edge_cycle(g, weight="weight") is True


# ---------------------------------------------------------------------------
# predecessor
# ---------------------------------------------------------------------------

class TestPredecessor:
    def test_simple(self, path_graph):
        preds = fnx.predecessor(path_graph, "a")
        assert preds["a"] == []  # source has no predecessors
        assert preds["b"] == ["a"]
        assert preds["c"] == ["b"]

    def test_with_cutoff(self, path_graph):
        preds = fnx.predecessor(path_graph, "a", cutoff=2)
        assert "b" in preds
        assert "c" in preds
        assert "d" not in preds

    def test_multiple_predecessors(self):
        """Diamond graph: a-b, a-c, b-d, c-d — d has two predecessors."""
        g = fnx.Graph()
        g.add_edge("a", "b")
        g.add_edge("a", "c")
        g.add_edge("b", "d")
        g.add_edge("c", "d")
        preds = fnx.predecessor(g, "a")
        assert sorted(preds["d"]) == ["b", "c"]


# ---------------------------------------------------------------------------
# path_weight
# ---------------------------------------------------------------------------

class TestPathWeight:
    def test_unweighted(self, path_graph):
        assert fnx.path_weight(path_graph, ["a", "b", "c"], weight="weight") == 2.0

    def test_weighted(self, weighted_triangle):
        assert fnx.path_weight(weighted_triangle, ["a", "b", "c"], weight="weight") == 5.0

    def test_single_node(self, path_graph):
        assert fnx.path_weight(path_graph, ["a"], weight="weight") == 0.0

    def test_empty(self, path_graph):
        assert fnx.path_weight(path_graph, [], weight="weight") == 0.0

    def test_missing_edge(self, disconnected_graph):
        with pytest.raises(fnx.NetworkXNoPath):
            fnx.path_weight(disconnected_graph, ["a", "b"], weight="weight")

    def test_directed_graph(self):
        g = fnx.DiGraph()
        g.add_edge("a", "b", weight=3.0)
        g.add_edge("b", "c", weight=4.0)
        assert fnx.path_weight(g, ["a", "b", "c"], weight="weight") == 7.0


# ---------------------------------------------------------------------------
# Integration: cross-algorithm consistency
# ---------------------------------------------------------------------------

class TestCrossAlgorithmConsistency:
    """Verify that different algorithms agree on the same graph."""

    def test_dijkstra_vs_bellman_ford(self, weighted_triangle):
        d1 = fnx.dijkstra_path_length(weighted_triangle, "a", "c", weight="weight")
        d2 = fnx.bellman_ford_path_length(weighted_triangle, "a", "c", weight="weight")
        assert d1 == d2

    def test_dijkstra_vs_floyd_warshall(self, weighted_triangle):
        d1 = fnx.dijkstra_path_length(weighted_triangle, "a", "c", weight="weight")
        fw = fnx.floyd_warshall(weighted_triangle, weight="weight")
        assert d1 == fw["a"]["c"]

    def test_single_source_vs_all_pairs(self, path_graph):
        ss = fnx.single_source_dijkstra_path_length(path_graph, "a", weight="weight")
        ap = dict(fnx.all_pairs_dijkstra_path_length(path_graph, weight="weight"))
        for node in ss:
            assert ss[node] == ap["a"][node]

    def test_bidirectional_vs_dijkstra(self, path_graph):
        bidir = fnx.bidirectional_shortest_path(path_graph, "a", "d")
        d_path = fnx.dijkstra_path(path_graph, "a", "d", weight="weight")
        assert len(bidir) == len(d_path)  # same length path
