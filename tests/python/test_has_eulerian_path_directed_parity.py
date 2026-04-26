"""Parity for ``has_eulerian_path`` on directed graphs.

Bead br-r37-c1-bf1wb. fnx.has_eulerian_path(DiGraph) raised
NetworkXNotImplemented('not implemented for directed type'). nx
supports both directed and undirected — a directed graph has an
Eulerian path iff at most one node has (out_degree - in_degree) = 1,
at most one has -1, all others 0, AND the underlying undirected graph
is connected.

fnx.is_eulerian on directed graphs already worked correctly; only
has_eulerian_path was over-restricted.
"""

from __future__ import annotations

import pytest

import franken_networkx as fnx

try:
    import networkx as nx
    HAS_NX = True
except ImportError:
    HAS_NX = False

needs_nx = pytest.mark.skipif(not HAS_NX, reason="networkx not installed")


# ---------------------------------------------------------------------------
# Directed graphs — must NOT raise; values must match nx
# ---------------------------------------------------------------------------

@needs_nx
def test_directed_cycle_has_eulerian_path():
    """A directed cycle is trivially Eulerian (every node in=out=1)."""
    DG = fnx.DiGraph([(0, 1), (1, 2), (2, 0)])
    DGX = nx.DiGraph([(0, 1), (1, 2), (2, 0)])
    assert fnx.has_eulerian_path(DG) == nx.has_eulerian_path(DGX) is True


@needs_nx
def test_directed_path_has_eulerian_path():
    """A directed path has an Eulerian path from source to sink."""
    DG = fnx.DiGraph([(0, 1), (1, 2)])
    DGX = nx.DiGraph([(0, 1), (1, 2)])
    assert fnx.has_eulerian_path(DG) == nx.has_eulerian_path(DGX) is True


@needs_nx
def test_directed_branching_no_eulerian_path():
    """A digraph with two outgoing edges from one node has no Eulerian path."""
    DG = fnx.DiGraph([(0, 1), (0, 2)])
    DGX = nx.DiGraph([(0, 1), (0, 2)])
    assert fnx.has_eulerian_path(DG) == nx.has_eulerian_path(DGX) is False


@needs_nx
def test_directed_disconnected_no_eulerian_path():
    DG = fnx.DiGraph([(0, 1), (2, 3)])
    DGX = nx.DiGraph([(0, 1), (2, 3)])
    assert fnx.has_eulerian_path(DG) == nx.has_eulerian_path(DGX) is False


@needs_nx
def test_directed_with_source_kwarg():
    DG = fnx.DiGraph([(0, 1), (1, 2), (2, 0), (2, 3)])
    DGX = nx.DiGraph([(0, 1), (1, 2), (2, 0), (2, 3)])
    assert fnx.has_eulerian_path(DG, source=0) == nx.has_eulerian_path(DGX, source=0)


@needs_nx
def test_directed_does_not_raise_not_implemented():
    """Regression: must not raise the old NetworkXNotImplemented."""
    DG = fnx.DiGraph([(0, 1), (1, 2)])
    # Should not raise.
    fnx.has_eulerian_path(DG)


# ---------------------------------------------------------------------------
# Undirected graphs — regression check
# ---------------------------------------------------------------------------

@needs_nx
def test_undirected_path_unchanged():
    G = fnx.path_graph(3)
    GX = nx.path_graph(3)
    assert fnx.has_eulerian_path(G) == nx.has_eulerian_path(GX) is True


@needs_nx
def test_undirected_cycle_unchanged():
    G = fnx.cycle_graph(4)
    GX = nx.cycle_graph(4)
    assert fnx.has_eulerian_path(G) == nx.has_eulerian_path(GX) is True


@needs_nx
def test_undirected_K4_no_eulerian_path():
    """K4 has 4 nodes each with degree 3 — no Eulerian path."""
    G = fnx.complete_graph(4)
    GX = nx.complete_graph(4)
    assert fnx.has_eulerian_path(G) == nx.has_eulerian_path(GX) is False


@needs_nx
def test_multidigraph_has_eulerian_path():
    """MultiDiGraph also supported by nx."""
    MDG = fnx.MultiDiGraph([(0, 1), (1, 2), (2, 0)])
    MDGX = nx.MultiDiGraph([(0, 1), (1, 2), (2, 0)])
    assert fnx.has_eulerian_path(MDG) == nx.has_eulerian_path(MDGX)
