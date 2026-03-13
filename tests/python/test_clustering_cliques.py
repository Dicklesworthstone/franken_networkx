"""Tests for clustering and clique algorithm bindings.

Tests cover:
- all_triangles
- node_clique_number
- enumerate_all_cliques
- find_cliques_recursive
- chordal_graph_cliques
- make_max_clique_graph
- ring_of_cliques
"""

import pytest
import franken_networkx as fnx


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def triangle():
    g = fnx.Graph()
    g.add_edge("a", "b")
    g.add_edge("b", "c")
    g.add_edge("c", "a")
    return g


@pytest.fixture
def k4():
    g = fnx.Graph()
    for u, v in [("a", "b"), ("a", "c"), ("a", "d"), ("b", "c"), ("b", "d"), ("c", "d")]:
        g.add_edge(u, v)
    return g


@pytest.fixture
def path3():
    g = fnx.Graph()
    g.add_edge("a", "b")
    g.add_edge("b", "c")
    return g


@pytest.fixture
def diamond():
    """Diamond graph: a-b, a-c, b-c, b-d, c-d (two triangles sharing edge b-c)."""
    g = fnx.Graph()
    g.add_edge("a", "b")
    g.add_edge("a", "c")
    g.add_edge("b", "c")
    g.add_edge("b", "d")
    g.add_edge("c", "d")
    return g


# ---------------------------------------------------------------------------
# all_triangles
# ---------------------------------------------------------------------------

class TestAllTriangles:
    def test_triangle(self, triangle):
        tris = fnx.all_triangles(triangle)
        assert len(tris) == 1
        # The triangle should contain all three nodes
        tri_set = set(tris[0])
        assert tri_set == {"a", "b", "c"}

    def test_k4(self, k4):
        tris = fnx.all_triangles(k4)
        # K4 has C(4,3) = 4 triangles
        assert len(tris) == 4

    def test_path_no_triangles(self, path3):
        tris = fnx.all_triangles(path3)
        assert tris == []

    def test_diamond(self, diamond):
        tris = fnx.all_triangles(diamond)
        # Diamond has 2 triangles: (a,b,c) and (b,c,d)
        assert len(tris) == 2

    def test_empty_graph(self):
        g = fnx.Graph()
        assert fnx.all_triangles(g) == []

    def test_single_node(self):
        g = fnx.Graph()
        g.add_node("x")
        assert fnx.all_triangles(g) == []


# ---------------------------------------------------------------------------
# node_clique_number
# ---------------------------------------------------------------------------

class TestNodeCliqueNumber:
    def test_triangle(self, triangle):
        result = fnx.node_clique_number(triangle)
        # All nodes are in a 3-clique
        assert result["a"] == 3
        assert result["b"] == 3
        assert result["c"] == 3

    def test_k4(self, k4):
        result = fnx.node_clique_number(k4)
        for node in ["a", "b", "c", "d"]:
            assert result[node] == 4

    def test_path(self, path3):
        result = fnx.node_clique_number(path3)
        # Path nodes are in at most a 2-clique (edge)
        for node in ["a", "b", "c"]:
            assert result[node] == 2

    def test_isolated_node(self):
        g = fnx.Graph()
        g.add_node("x")
        result = fnx.node_clique_number(g)
        assert result["x"] == 1

    def test_diamond(self, diamond):
        result = fnx.node_clique_number(diamond)
        # a is in triangle (a,b,c) → clique number 3
        assert result["a"] == 3
        # d is in triangle (b,c,d) → clique number 3
        assert result["d"] == 3


# ---------------------------------------------------------------------------
# enumerate_all_cliques
# ---------------------------------------------------------------------------

class TestEnumerateAllCliques:
    def test_triangle(self, triangle):
        cliques = fnx.enumerate_all_cliques(triangle)
        # 3 single-node cliques + 3 edge cliques + 1 triangle = 7
        assert len(cliques) == 7
        sizes = [len(c) for c in cliques]
        assert sizes.count(1) == 3
        assert sizes.count(2) == 3
        assert sizes.count(3) == 1

    def test_path(self, path3):
        cliques = fnx.enumerate_all_cliques(path3)
        # 3 single nodes + 2 edges = 5
        assert len(cliques) == 5

    def test_k4(self, k4):
        cliques = fnx.enumerate_all_cliques(k4)
        # C(4,1) + C(4,2) + C(4,3) + C(4,4) = 4 + 6 + 4 + 1 = 15
        assert len(cliques) == 15

    def test_empty_graph(self):
        g = fnx.Graph()
        assert fnx.enumerate_all_cliques(g) == []

    def test_single_node(self):
        g = fnx.Graph()
        g.add_node("x")
        cliques = fnx.enumerate_all_cliques(g)
        assert len(cliques) == 1
        assert cliques[0] == ["x"]


# ---------------------------------------------------------------------------
# find_cliques_recursive
# ---------------------------------------------------------------------------

class TestFindCliquesRecursive:
    def test_triangle(self, triangle):
        cliques = fnx.find_cliques_recursive(triangle)
        assert len(cliques) == 1
        assert set(cliques[0]) == {"a", "b", "c"}

    def test_k4(self, k4):
        cliques = fnx.find_cliques_recursive(k4)
        assert len(cliques) == 1
        assert set(cliques[0]) == {"a", "b", "c", "d"}

    def test_matches_find_cliques(self, diamond):
        rec = fnx.find_cliques_recursive(diamond)
        iterative = fnx.find_cliques(diamond)
        # Both should return same cliques (sorted)
        assert sorted([sorted(c) for c in rec]) == sorted([sorted(c) for c in iterative])

    def test_path(self, path3):
        cliques = fnx.find_cliques_recursive(path3)
        # Two maximal cliques: {a,b} and {b,c}
        assert len(cliques) == 2

    def test_empty_graph(self):
        g = fnx.Graph()
        assert fnx.find_cliques_recursive(g) == []


# ---------------------------------------------------------------------------
# chordal_graph_cliques
# ---------------------------------------------------------------------------

class TestChordalGraphCliques:
    def test_triangle(self, triangle):
        cliques = fnx.chordal_graph_cliques(triangle)
        assert len(cliques) == 1
        assert set(cliques[0]) == {"a", "b", "c"}

    def test_path(self, path3):
        cliques = fnx.chordal_graph_cliques(path3)
        assert len(cliques) == 2

    def test_k4(self, k4):
        cliques = fnx.chordal_graph_cliques(k4)
        # K4 is chordal, one maximal clique
        assert len(cliques) == 1

    def test_self_loop_raises(self):
        g = fnx.Graph()
        g.add_edge("a", "a")
        with pytest.raises(fnx.NetworkXError):
            fnx.chordal_graph_cliques(g)


# ---------------------------------------------------------------------------
# make_max_clique_graph
# ---------------------------------------------------------------------------

class TestMakeMaxCliqueGraph:
    def test_triangle(self, triangle):
        mcg = fnx.make_max_clique_graph(triangle)
        # Triangle: 1 maximal clique → 1 node
        assert mcg.number_of_nodes() == 1
        assert mcg.number_of_edges() == 0

    def test_diamond(self, diamond):
        mcg = fnx.make_max_clique_graph(diamond)
        # Diamond: 2 maximal cliques sharing nodes → 2 nodes, 1 edge
        assert mcg.number_of_nodes() == 2
        assert mcg.number_of_edges() == 1

    def test_path(self, path3):
        mcg = fnx.make_max_clique_graph(path3)
        # Path a-b-c: 2 maximal cliques {a,b} and {b,c}, sharing b → edge
        assert mcg.number_of_nodes() == 2
        assert mcg.number_of_edges() == 1


# ---------------------------------------------------------------------------
# ring_of_cliques
# ---------------------------------------------------------------------------

class TestRingOfCliques:
    def test_basic(self):
        g = fnx.ring_of_cliques(3, 3)
        assert g.number_of_nodes() == 9
        assert g.number_of_edges() == 12

    def test_two_by_two(self):
        g = fnx.ring_of_cliques(2, 2)
        assert g.number_of_nodes() == 4
        assert g.number_of_edges() == 4

    def test_connected(self):
        g = fnx.ring_of_cliques(4, 3)
        assert fnx.is_connected(g)
