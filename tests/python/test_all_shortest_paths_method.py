"""Parity tests for all_shortest_paths method parameter (bead 8kb)."""
import pytest
import franken_networkx as fnx
import networkx as nx


@pytest.fixture
def weighted_graph():
    G = fnx.Graph()
    G.add_edge(0, 1, weight=1)
    G.add_edge(1, 2, weight=1)
    G.add_edge(0, 2, weight=3)
    return G


@pytest.fixture
def nx_weighted_graph():
    G = nx.Graph()
    G.add_edge(0, 1, weight=1)
    G.add_edge(1, 2, weight=1)
    G.add_edge(0, 2, weight=3)
    return G


class TestAllShortestPathsMethod:
    def test_default_unweighted(self, weighted_graph, nx_weighted_graph):
        """Default (no weight) uses BFS — should find direct edge 0→2."""
        paths = list(fnx.all_shortest_paths(weighted_graph, 0, 2))
        npaths = list(nx.all_shortest_paths(nx_weighted_graph, 0, 2))
        assert paths == npaths

    def test_dijkstra_weighted(self, weighted_graph, nx_weighted_graph):
        """With weight='weight', Dijkstra finds 0→1→2 (cost 2) over 0→2 (cost 3)."""
        paths = list(fnx.all_shortest_paths(weighted_graph, 0, 2, weight="weight"))
        npaths = list(nx.all_shortest_paths(nx_weighted_graph, 0, 2, weight="weight"))
        assert paths == npaths
        assert paths == [[0, 1, 2]]

    def test_explicit_dijkstra(self, weighted_graph):
        """method='dijkstra' should behave same as default weighted."""
        paths = list(
            fnx.all_shortest_paths(
                weighted_graph, 0, 2, weight="weight", method="dijkstra"
            )
        )
        assert paths == [[0, 1, 2]]

    def test_bellman_ford_undirected_raises(self, weighted_graph):
        """method='bellman-ford' on undirected graph should raise (negative cycle risk)."""
        with pytest.raises(NotImplementedError):
            list(
                fnx.all_shortest_paths(
                    weighted_graph, 0, 2, weight="weight", method="bellman-ford"
                )
            )

    def test_unweighted_method_explicit(self, weighted_graph, nx_weighted_graph):
        """method='unweighted' ignores edge weights."""
        paths = list(fnx.all_shortest_paths(weighted_graph, 0, 2, method="unweighted"))
        npaths = list(nx.all_shortest_paths(nx_weighted_graph, 0, 2))
        assert paths == npaths

    def test_multiple_shortest_paths(self):
        """Graph with multiple shortest paths returns all of them."""
        G = fnx.Graph()
        G.add_edges_from([(0, 1), (0, 2), (1, 3), (2, 3)])
        nG = nx.Graph(G.edges())
        paths = sorted(fnx.all_shortest_paths(G, 0, 3))
        npaths = sorted(nx.all_shortest_paths(nG, 0, 3))
        assert paths == npaths
        assert len(paths) == 2

    def test_no_path_raises(self):
        """Missing path raises NetworkXNoPath."""
        G = fnx.Graph()
        G.add_nodes_from([0, 1])
        with pytest.raises(fnx.NetworkXNoPath):
            list(fnx.all_shortest_paths(G, 0, 1))
