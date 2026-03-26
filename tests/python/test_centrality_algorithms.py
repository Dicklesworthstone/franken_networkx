"""Tests for additional centrality algorithm bindings.

Tests cover:
- in_degree_centrality
- out_degree_centrality
- local_reaching_centrality
- global_reaching_centrality
- group_degree_centrality
- group_in_degree_centrality
- group_out_degree_centrality
"""

import pytest
import franken_networkx as fnx


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def directed_chain():
    """a->b->c."""
    g = fnx.DiGraph()
    g.add_edge("a", "b")
    g.add_edge("b", "c")
    return g


@pytest.fixture
def directed_cycle():
    """a->b->c->a."""
    g = fnx.DiGraph()
    g.add_edge("a", "b")
    g.add_edge("b", "c")
    g.add_edge("c", "a")
    return g


@pytest.fixture
def triangle():
    g = fnx.Graph()
    g.add_edge("a", "b")
    g.add_edge("b", "c")
    g.add_edge("c", "a")
    return g


# ---------------------------------------------------------------------------
# in_degree_centrality
# ---------------------------------------------------------------------------

class TestInDegreeCentrality:
    def test_chain(self, directed_chain):
        dc = fnx.in_degree_centrality(directed_chain)
        assert dc["a"] == pytest.approx(0.0)
        assert dc["b"] == pytest.approx(0.5)
        assert dc["c"] == pytest.approx(0.5)

    def test_cycle(self, directed_cycle):
        dc = fnx.in_degree_centrality(directed_cycle)
        # Each node has in-degree 1, n-1=2
        for v in ["a", "b", "c"]:
            assert dc[v] == pytest.approx(0.5)

    def test_raises_on_undirected(self, triangle):
        with pytest.raises(fnx.NetworkXNotImplemented):
            fnx.in_degree_centrality(triangle)


# ---------------------------------------------------------------------------
# out_degree_centrality
# ---------------------------------------------------------------------------

class TestOutDegreeCentrality:
    def test_chain(self, directed_chain):
        dc = fnx.out_degree_centrality(directed_chain)
        assert dc["a"] == pytest.approx(0.5)
        assert dc["b"] == pytest.approx(0.5)
        assert dc["c"] == pytest.approx(0.0)

    def test_complementary(self, directed_cycle):
        """In a regular digraph, in and out degree centrality should match."""
        in_dc = fnx.in_degree_centrality(directed_cycle)
        out_dc = fnx.out_degree_centrality(directed_cycle)
        for v in ["a", "b", "c"]:
            assert in_dc[v] == pytest.approx(out_dc[v])


# ---------------------------------------------------------------------------
# local_reaching_centrality
# ---------------------------------------------------------------------------

class TestLocalReachingCentrality:
    def test_connected_undirected(self, triangle):
        assert fnx.local_reaching_centrality(triangle, "a") == pytest.approx(1.0)

    def test_disconnected_undirected(self):
        g = fnx.Graph()
        g.add_edge("a", "b")
        g.add_node("c")
        assert fnx.local_reaching_centrality(g, "a") == pytest.approx(0.5)

    def test_directed_chain(self, directed_chain):
        assert fnx.local_reaching_centrality(directed_chain, "a") == pytest.approx(1.0)
        assert fnx.local_reaching_centrality(directed_chain, "c") == pytest.approx(0.0)

    def test_directed_middle(self, directed_chain):
        assert fnx.local_reaching_centrality(directed_chain, "b") == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# global_reaching_centrality
# ---------------------------------------------------------------------------

class TestGlobalReachingCentrality:
    def test_connected_undirected(self, triangle):
        # All nodes reach all others: GRC = 0
        assert fnx.global_reaching_centrality(triangle) == pytest.approx(0.0)

    def test_directed_chain(self, directed_chain):
        # local reaching = [1.0, 0.5, 0.0], max=1.0
        # GRC = ((0) + (0.5) + (1.0)) / 2 = 0.75
        assert fnx.global_reaching_centrality(directed_chain) == pytest.approx(0.75)


# ---------------------------------------------------------------------------
# group_degree_centrality
# ---------------------------------------------------------------------------

class TestGroupDegreeCentrality:
    def test_single_node_triangle(self, triangle):
        # {a} neighbors outside = {b,c}, non-group=2, so 1.0
        assert fnx.group_degree_centrality(triangle, ["a"]) == pytest.approx(1.0)

    def test_disconnected(self):
        g = fnx.Graph()
        g.add_edge("a", "b")
        g.add_node("c")
        # {a} neighbors outside = {b}, non-group=2, so 0.5
        assert fnx.group_degree_centrality(g, ["a"]) == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# group_in_degree_centrality
# ---------------------------------------------------------------------------

class TestGroupInDegreeCentrality:
    def test_simple(self):
        g = fnx.DiGraph()
        g.add_edge("a", "b")
        g.add_edge("c", "b")
        # Group {b}: predecessors outside = {a,c}, non-group=2
        assert fnx.group_in_degree_centrality(g, ["b"]) == pytest.approx(1.0)

    def test_raises_on_undirected(self, triangle):
        with pytest.raises(fnx.NetworkXNotImplemented):
            fnx.group_in_degree_centrality(triangle, ["a"])


# ---------------------------------------------------------------------------
# group_out_degree_centrality
# ---------------------------------------------------------------------------

class TestGroupOutDegreeCentrality:
    def test_simple(self):
        g = fnx.DiGraph()
        g.add_edge("a", "b")
        g.add_edge("a", "c")
        # Group {a}: successors outside = {b,c}, non-group=2
        assert fnx.group_out_degree_centrality(g, ["a"]) == pytest.approx(1.0)

    def test_raises_on_undirected(self, triangle):
        with pytest.raises(fnx.NetworkXNotImplemented):
            fnx.group_out_degree_centrality(triangle, ["a"])
