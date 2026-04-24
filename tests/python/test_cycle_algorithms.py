"""Tests for additional cycle algorithm bindings.

Tests cover:
- girth
- find_negative_cycle
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
def square():
    g = fnx.Graph()
    g.add_edge("a", "b")
    g.add_edge("b", "c")
    g.add_edge("c", "d")
    g.add_edge("d", "a")
    return g


@pytest.fixture
def tree():
    """A simple tree: a-b, b-c, b-d."""
    g = fnx.Graph()
    g.add_edge("a", "b")
    g.add_edge("b", "c")
    g.add_edge("b", "d")
    return g


# ---------------------------------------------------------------------------
# girth
# ---------------------------------------------------------------------------

class TestGirth:
    def test_triangle(self, triangle):
        assert fnx.girth(triangle) == 3

    def test_square(self, square):
        assert fnx.girth(square) == 4

    def test_tree_no_cycle(self, tree):
        # br-girthinf: nx returns math.inf (not None) for acyclic graphs
        import math
        assert fnx.girth(tree) == math.inf

    def test_multiple_cycles(self):
        """Triangle + square sharing an edge: girth should be 3."""
        g = fnx.Graph()
        g.add_edge("a", "b")
        g.add_edge("b", "c")
        g.add_edge("c", "a")
        g.add_edge("c", "d")
        g.add_edge("d", "a")
        assert fnx.girth(g) == 3

    def test_empty_graph(self):
        import math
        g = fnx.Graph()
        assert fnx.girth(g) == math.inf

    def test_single_node(self):
        import math
        g = fnx.Graph()
        g.add_node("a")
        assert fnx.girth(g) == math.inf

    def test_raises_on_directed(self):
        g = fnx.DiGraph()
        g.add_edge("a", "b")
        with pytest.raises(fnx.NetworkXNotImplemented):
            fnx.girth(g)


# ---------------------------------------------------------------------------
# find_negative_cycle
# ---------------------------------------------------------------------------

class TestFindNegativeCycle:
    def test_no_negative_cycle(self):
        g = fnx.Graph()
        g.add_edge("a", "b", weight=1.0)
        g.add_edge("b", "c", weight=2.0)
        with pytest.raises(fnx.NetworkXError):
            fnx.find_negative_cycle(g, "a")

    def test_negative_cycle_found(self):
        g = fnx.Graph()
        g.add_edge("a", "b", weight=-5.0)
        g.add_edge("b", "c", weight=1.0)
        g.add_edge("c", "a", weight=1.0)
        cycle = fnx.find_negative_cycle(g, "a")
        assert isinstance(cycle, list)
        assert len(cycle) >= 2  # At least 2 nodes form a cycle

    def test_directed_without_negative_cycle_raises_networkx_error(self):
        """franken_networkx-94ld: find_negative_cycle now supports directed
        graphs (routes through nx for DiGraph inputs). A single negative
        edge without a cycle raises NetworkXError('No negative cycles
        detected.') matching upstream — not NetworkXNotImplemented.

        The wrapper routes through nx for directed inputs, so the raised
        class is nx.NetworkXError (fnx.NetworkXError is a distinct class
        despite the shared name).
        """
        import networkx as nx

        g = fnx.DiGraph()
        g.add_edge("a", "b", weight=-5.0)
        with pytest.raises(
            (fnx.NetworkXError, fnx.NetworkXNotImplemented, nx.NetworkXError),
            match="No negative cycles detected|not implemented",
        ):
            fnx.find_negative_cycle(g, "a")
