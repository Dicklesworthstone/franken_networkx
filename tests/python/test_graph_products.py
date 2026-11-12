"""Tests for line_graph, cartesian_product, and tensor_product."""

import pytest

import franken_networkx as fnx


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def triangle():
    """Triangle graph: 0-1, 1-2, 0-2."""
    G = fnx.Graph()
    G.add_edge(0, 1)
    G.add_edge(1, 2)
    G.add_edge(0, 2)
    return G


@pytest.fixture
def path3():
    """Path graph: 0-1-2."""
    G = fnx.Graph()
    G.add_edge(0, 1)
    G.add_edge(1, 2)
    return G


@pytest.fixture
def k2():
    """Complete graph K2: 0-1."""
    G = fnx.Graph()
    G.add_edge(0, 1)
    return G


@pytest.fixture
def path2_directed():
    """Directed path: 0->1."""
    D = fnx.DiGraph()
    D.add_edge(0, 1)
    return D


# ---------------------------------------------------------------------------
# line_graph tests
# ---------------------------------------------------------------------------


class TestLineGraph:
    def test_line_graph_triangle(self, triangle):
        L = fnx.line_graph(triangle)
        # Triangle has 3 edges, so L has 3 nodes
        # All edges are adjacent (share vertices), so L is also a triangle
        assert L.number_of_nodes() == 3
        assert L.number_of_edges() == 3

    def test_line_graph_path(self, path3):
        L = fnx.line_graph(path3)
        # Path 0-1-2 has 2 edges, sharing vertex 1
        assert L.number_of_nodes() == 2
        assert L.number_of_edges() == 1

    def test_line_graph_single_edge(self, k2):
        L = fnx.line_graph(k2)
        assert L.number_of_nodes() == 1
        assert L.number_of_edges() == 0

    def test_line_graph_empty(self):
        G = fnx.Graph()
        G.add_node(0)
        L = fnx.line_graph(G)
        assert L.number_of_nodes() == 0
        assert L.number_of_edges() == 0

    def test_line_graph_directed(self, path2_directed):
        L = fnx.line_graph(path2_directed)
        # Single directed edge -> single node, no edges
        assert L.number_of_nodes() == 1
        assert L.number_of_edges() == 0

    def test_line_graph_directed_path(self):
        D = fnx.DiGraph()
        D.add_edge(0, 1)
        D.add_edge(1, 2)
        L = fnx.line_graph(D)
        # Two edges (0,1) and (1,2), head of first = tail of second
        assert L.number_of_nodes() == 2
        assert L.number_of_edges() == 1


# ---------------------------------------------------------------------------
# cartesian_product tests
# ---------------------------------------------------------------------------


class TestCartesianProduct:
    def test_cartesian_product_k2_k2(self, k2):
        # K2 x K2 = 4-cycle (C4)
        P = fnx.cartesian_product(k2, k2)
        assert P.number_of_nodes() == 4
        assert P.number_of_edges() == 4

    def test_cartesian_product_empty(self):
        G1 = fnx.Graph()
        G2 = fnx.Graph()
        G1.add_node(0)
        G2.add_node(0)
        P = fnx.cartesian_product(G1, G2)
        assert P.number_of_nodes() == 1
        assert P.number_of_edges() == 0

    def test_cartesian_product_one_edge(self, k2, path3):
        # K2 (1 edge) x P3 (2 edges)
        # Nodes: 2 x 3 = 6
        # Edges: for each of 2 nodes in K2, 2 edges in P3 = 4
        #      + for each of 3 nodes in P3, 1 edge in K2 = 3
        #      = 7 edges total
        P = fnx.cartesian_product(k2, path3)
        assert P.number_of_nodes() == 6
        assert P.number_of_edges() == 7

    def test_cartesian_product_directed(self, path2_directed):
        D = fnx.DiGraph()
        D.add_edge(0, 1)
        P = fnx.cartesian_product(path2_directed, D)
        assert P.number_of_nodes() == 4
        # 2 nodes in D1, 1 directed edge in D2 = 2 edges
        # 2 nodes in D2, 1 directed edge in D1 = 2 edges
        # Total = 4 directed edges
        assert P.number_of_edges() == 4


# ---------------------------------------------------------------------------
# tensor_product tests
# ---------------------------------------------------------------------------


class TestTensorProduct:
    def test_tensor_product_k2_k2(self, k2):
        # K2 x K2 has 4 nodes but forms 2 disjoint edges
        P = fnx.tensor_product(k2, k2)
        assert P.number_of_nodes() == 4
        # Edge {0,1} in both graphs creates edges:
        # (0,0)-(1,1) and (0,1)-(1,0)
        assert P.number_of_edges() == 2

    def test_tensor_product_empty_edges(self, k2):
        G = fnx.Graph()
        G.add_node(0)
        G.add_node(1)
        # No edges in G -> no edges in tensor product
        P = fnx.tensor_product(k2, G)
        assert P.number_of_nodes() == 4
        assert P.number_of_edges() == 0

    def test_tensor_product_triangle_edge(self, triangle, k2):
        # Triangle has 3 edges, K2 has 1 edge
        # For each pair of edges, we get 2 edges in tensor product
        # But we need to be careful about counting
        P = fnx.tensor_product(triangle, k2)
        assert P.number_of_nodes() == 6
        # Each edge in triangle (3) paired with edge in K2 (1)
        # gives 2 edges each = 6 edges
        assert P.number_of_edges() == 6

    def test_tensor_product_directed(self, path2_directed):
        D = fnx.DiGraph()
        D.add_edge(0, 1)
        P = fnx.tensor_product(path2_directed, D)
        assert P.number_of_nodes() == 4
        # Only (0,0) -> (1,1) edge
        assert P.number_of_edges() == 1


# ---------------------------------------------------------------------------
# Error cases
# ---------------------------------------------------------------------------


class TestErrors:
    def test_mixed_types_cartesian(self, k2, path2_directed):
        # Cannot mix directed and undirected
        with pytest.raises(fnx.NetworkXError):
            fnx.cartesian_product(k2, path2_directed)

    def test_mixed_types_tensor(self, k2, path2_directed):
        with pytest.raises(fnx.NetworkXError):
            fnx.tensor_product(k2, path2_directed)
