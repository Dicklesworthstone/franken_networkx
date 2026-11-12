"""Tests for additional matching algorithm bindings.

Tests cover:
- is_edge_cover
- max_weight_clique
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
def path3():
    g = fnx.Graph()
    g.add_edge("a", "b")
    g.add_edge("b", "c")
    return g


# ---------------------------------------------------------------------------
# is_edge_cover
# ---------------------------------------------------------------------------

class TestIsEdgeCover:
    def test_valid(self, path3):
        assert fnx.is_edge_cover(path3, [("a", "b"), ("b", "c")]) is True

    def test_missing_node(self, path3):
        assert fnx.is_edge_cover(path3, [("a", "b")]) is False

    def test_triangle_single_cover(self, triangle):
        # Two edges can cover all 3 nodes
        assert fnx.is_edge_cover(triangle, [("a", "b"), ("b", "c")]) is True

    def test_empty_graph(self):
        g = fnx.Graph()
        assert fnx.is_edge_cover(g, []) is True

    def test_invalid_edge(self):
        g = fnx.Graph()
        g.add_edge("a", "b")
        g.add_node("c")
        assert fnx.is_edge_cover(g, [("a", "c")]) is False


# ---------------------------------------------------------------------------
# max_weight_clique
# ---------------------------------------------------------------------------

class TestMaxWeightClique:
    # br-r37-c1-puznv: max_weight_clique defaults to weight="weight"
    # (matches nx); calling it on nodes that don't carry that attr
    # raises KeyError in both fnx and nx.  These tests intentionally
    # check the unweighted node-count behaviour, which is what
    # ``weight=None`` selects.
    def test_triangle(self, triangle):
        clique, weight = fnx.max_weight_clique(triangle, weight=None)
        assert set(clique) == {"a", "b", "c"}
        assert weight == pytest.approx(3.0)

    def test_path_is_edge(self, path3):
        clique, weight = fnx.max_weight_clique(path3, weight=None)
        assert len(clique) == 2
        assert weight == pytest.approx(2.0)

    def test_empty(self):
        g = fnx.Graph()
        clique, weight = fnx.max_weight_clique(g, weight=None)
        assert clique == []
        assert weight == pytest.approx(0.0)

    def test_single_node(self):
        g = fnx.Graph()
        g.add_node("a")
        clique, weight = fnx.max_weight_clique(g, weight=None)
        assert clique == ["a"]
        assert weight == pytest.approx(1.0)
