"""Conformance tests for is_k_regular comparing FrankenNetworkX against NetworkX."""

import pytest
import networkx as nx
import franken_networkx as fnx


def fnx_from_nx(nx_graph):
    """Convert NetworkX graph to FrankenNetworkX graph."""
    if nx_graph.is_directed():
        fnx_graph = fnx.DiGraph()
    else:
        fnx_graph = fnx.Graph()
    fnx_graph.add_nodes_from(nx_graph.nodes())
    fnx_graph.add_edges_from(nx_graph.edges())
    return fnx_graph


class TestIsKRegularConformance:
    """Test is_k_regular matches NetworkX behavior exactly."""

    def test_complete_graph_is_n_minus_1_regular(self):
        """Complete graph K_n is (n-1)-regular."""
        for n in range(2, 8):
            nx_g = nx.complete_graph(n)
            fnx_g = fnx_from_nx(nx_g)
            k = n - 1
            assert nx.is_k_regular(nx_g, k) == fnx.is_k_regular(fnx_g, k)
            assert fnx.is_k_regular(fnx_g, k) is True

    def test_complete_graph_not_other_k_regular(self):
        """Complete graph K_n is not k-regular for k != n-1."""
        for n in range(3, 6):
            nx_g = nx.complete_graph(n)
            fnx_g = fnx_from_nx(nx_g)
            for k in range(0, n + 2):
                if k != n - 1:
                    assert nx.is_k_regular(nx_g, k) == fnx.is_k_regular(fnx_g, k)
                    assert fnx.is_k_regular(fnx_g, k) is False

    def test_cycle_graph_is_2_regular(self):
        """Cycle graph C_n is 2-regular for n >= 3."""
        for n in range(3, 10):
            nx_g = nx.cycle_graph(n)
            fnx_g = fnx_from_nx(nx_g)
            assert nx.is_k_regular(nx_g, 2) == fnx.is_k_regular(fnx_g, 2)
            assert fnx.is_k_regular(fnx_g, 2) is True
            assert fnx.is_k_regular(fnx_g, 1) is False
            assert fnx.is_k_regular(fnx_g, 3) is False

    def test_path_graph_not_regular(self):
        """Path graph P_n is not k-regular for any k when n > 2."""
        for n in range(3, 8):
            nx_g = nx.path_graph(n)
            fnx_g = fnx_from_nx(nx_g)
            for k in range(0, n):
                assert nx.is_k_regular(nx_g, k) == fnx.is_k_regular(fnx_g, k)
                assert fnx.is_k_regular(fnx_g, k) is False

    def test_empty_graph_is_0_regular(self):
        """Empty graph (no edges) is 0-regular."""
        for n in range(1, 6):
            nx_g = nx.empty_graph(n)
            fnx_g = fnx_from_nx(nx_g)
            assert nx.is_k_regular(nx_g, 0) == fnx.is_k_regular(fnx_g, 0)
            assert fnx.is_k_regular(fnx_g, 0) is True
            if n > 0:
                assert fnx.is_k_regular(fnx_g, 1) is False

    def test_star_graph_not_regular(self):
        """Star graph S_n is not regular for n > 1."""
        for n in range(2, 7):
            nx_g = nx.star_graph(n)
            fnx_g = fnx_from_nx(nx_g)
            for k in range(0, n + 2):
                assert nx.is_k_regular(nx_g, k) == fnx.is_k_regular(fnx_g, k)

    def test_petersen_graph_is_3_regular(self):
        """Petersen graph is 3-regular."""
        nx_g = nx.petersen_graph()
        fnx_g = fnx_from_nx(nx_g)
        assert nx.is_k_regular(nx_g, 3) == fnx.is_k_regular(fnx_g, 3)
        assert fnx.is_k_regular(fnx_g, 3) is True
        assert fnx.is_k_regular(fnx_g, 2) is False
        assert fnx.is_k_regular(fnx_g, 4) is False

    def test_cube_graph_is_3_regular(self):
        """Hypercube Q_3 (cube graph) is 3-regular."""
        nx_g = nx.hypercube_graph(3)
        fnx_g = fnx_from_nx(nx_g)
        assert nx.is_k_regular(nx_g, 3) == fnx.is_k_regular(fnx_g, 3)
        assert fnx.is_k_regular(fnx_g, 3) is True

    def test_hypercube_is_n_regular(self):
        """Hypercube Q_n is n-regular."""
        for n in range(1, 5):
            nx_g = nx.hypercube_graph(n)
            fnx_g = fnx_from_nx(nx_g)
            assert nx.is_k_regular(nx_g, n) == fnx.is_k_regular(fnx_g, n)
            assert fnx.is_k_regular(fnx_g, n) is True

    def test_single_node_is_0_regular(self):
        """Single node graph is 0-regular."""
        nx_g = nx.Graph()
        nx_g.add_node(0)
        fnx_g = fnx.Graph()
        fnx_g.add_node(0)
        assert nx.is_k_regular(nx_g, 0) == fnx.is_k_regular(fnx_g, 0)
        assert fnx.is_k_regular(fnx_g, 0) is True

    def test_single_edge_not_regular(self):
        """Single edge graph (2 nodes, 1 edge) is 1-regular."""
        nx_g = nx.Graph([(0, 1)])
        fnx_g = fnx.Graph([(0, 1)])
        assert nx.is_k_regular(nx_g, 1) == fnx.is_k_regular(fnx_g, 1)
        assert fnx.is_k_regular(fnx_g, 1) is True
        assert fnx.is_k_regular(fnx_g, 0) is False

    def test_self_loop_affects_regularity(self):
        """Self-loop adds to degree, affecting regularity."""
        nx_g = nx.Graph()
        nx_g.add_edge(0, 0)  # self-loop
        fnx_g = fnx.Graph()
        fnx_g.add_edge(0, 0)
        # Self-loop adds 2 to degree in NetworkX
        nx_result = nx.is_k_regular(nx_g, 2)
        fnx_result = fnx.is_k_regular(fnx_g, 2)
        assert nx_result == fnx_result

    def test_regular_bipartite_graph(self):
        """Regular bipartite graph is k-regular."""
        nx_g = nx.complete_bipartite_graph(3, 3)  # 3-regular
        fnx_g = fnx_from_nx(nx_g)
        assert nx.is_k_regular(nx_g, 3) == fnx.is_k_regular(fnx_g, 3)
        assert fnx.is_k_regular(fnx_g, 3) is True

    def test_wheel_graph_not_regular(self):
        """Wheel graph W_n is not regular for n > 3."""
        for n in range(4, 8):
            nx_g = nx.wheel_graph(n)
            fnx_g = fnx_from_nx(nx_g)
            for k in range(0, n + 1):
                assert nx.is_k_regular(nx_g, k) == fnx.is_k_regular(fnx_g, k)

    def test_negative_k_raises_or_returns_false(self):
        """Negative k should match NetworkX behavior."""
        nx_g = nx.complete_graph(4)
        fnx_g = fnx_from_nx(nx_g)
        try:
            nx_result = nx.is_k_regular(nx_g, -1)
            fnx_result = fnx.is_k_regular(fnx_g, -1)
            assert nx_result == fnx_result
        except (ValueError, nx.NetworkXError) as e:
            with pytest.raises((ValueError, fnx.NetworkXError)):
                fnx.is_k_regular(fnx_g, -1)

    def test_k_larger_than_nodes_returns_false(self):
        """k larger than n-1 should return False."""
        nx_g = nx.complete_graph(5)
        fnx_g = fnx_from_nx(nx_g)
        assert nx.is_k_regular(nx_g, 10) == fnx.is_k_regular(fnx_g, 10)
        assert fnx.is_k_regular(fnx_g, 10) is False

    def test_circulant_graphs_are_regular(self):
        """Circulant graphs C_n(offsets) are regular."""
        nx_g = nx.circulant_graph(8, [1, 2])  # 4-regular
        fnx_g = fnx_from_nx(nx_g)
        assert nx.is_k_regular(nx_g, 4) == fnx.is_k_regular(fnx_g, 4)
        assert fnx.is_k_regular(fnx_g, 4) is True

    def test_turan_graph_regularity(self):
        """Turan graph T(n,r) regularity check."""
        nx_g = nx.turan_graph(6, 2)  # Complete bipartite K_3,3
        fnx_g = fnx_from_nx(nx_g)
        assert nx.is_k_regular(nx_g, 3) == fnx.is_k_regular(fnx_g, 3)
