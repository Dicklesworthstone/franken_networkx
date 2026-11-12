"""Parity for ``eulerian_path`` on directed graphs.

Bead br-r37-c1-z4i7f. fnx.eulerian_path(DiGraph) raised
NetworkXNotImplemented('not implemented for directed type'). nx
supports directed Eulerian paths and raises ``NetworkXError('Graph
has no Eulerian paths.')`` only when the graph genuinely lacks one.
Drop-in code that called eulerian_path(digraph) broke. Same fix
pattern as br-r37-c1-bf1wb (has_eulerian_path).
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
# Directed: yields the path
# ---------------------------------------------------------------------------

@needs_nx
def test_directed_path_yields_edges_in_order():
    DG = fnx.DiGraph([(0, 1), (1, 2)])
    DGX = nx.DiGraph([(0, 1), (1, 2)])
    assert list(fnx.eulerian_path(DG)) == list(nx.eulerian_path(DGX)) == [(0, 1), (1, 2)]


@needs_nx
def test_directed_cycle_yields_traversal():
    DG = fnx.DiGraph([(0, 1), (1, 2), (2, 0)])
    DGX = nx.DiGraph([(0, 1), (1, 2), (2, 0)])
    assert list(fnx.eulerian_path(DG)) == list(nx.eulerian_path(DGX))


@needs_nx
def test_directed_branching_raises_no_eulerian_paths():
    """A digraph with two outgoing from one node has no Eulerian path."""
    DG = fnx.DiGraph([(0, 1), (0, 2)])
    DGX = nx.DiGraph([(0, 1), (0, 2)])
    with pytest.raises(fnx.NetworkXError) as fnx_exc:
        list(fnx.eulerian_path(DG))
    with pytest.raises(nx.NetworkXError) as nx_exc:
        list(nx.eulerian_path(DGX))
    assert str(fnx_exc.value) == str(nx_exc.value) == "Graph has no Eulerian paths."


@needs_nx
def test_directed_does_not_raise_not_implemented():
    """Regression: must not raise the old NetworkXNotImplemented."""
    DG = fnx.DiGraph([(0, 1), (1, 2)])
    list(fnx.eulerian_path(DG))


@needs_nx
def test_directed_with_source_kwarg():
    DG = fnx.DiGraph([(0, 1), (1, 2)])
    DGX = nx.DiGraph([(0, 1), (1, 2)])
    assert list(fnx.eulerian_path(DG, source=0)) == list(
        nx.eulerian_path(DGX, source=0)
    )


# ---------------------------------------------------------------------------
# MultiDiGraph + keys=True
# ---------------------------------------------------------------------------

@needs_nx
def test_multidigraph_yields_eulerian_path():
    MDG = fnx.MultiDiGraph([(0, 1), (1, 2), (2, 0)])
    MDGX = nx.MultiDiGraph([(0, 1), (1, 2), (2, 0)])
    assert list(fnx.eulerian_path(MDG)) == list(nx.eulerian_path(MDGX))


@needs_nx
def test_multidigraph_keys_true():
    MDG = fnx.MultiDiGraph([(0, 1), (1, 2), (2, 0)])
    MDGX = nx.MultiDiGraph([(0, 1), (1, 2), (2, 0)])
    assert list(fnx.eulerian_path(MDG, keys=True)) == list(
        nx.eulerian_path(MDGX, keys=True)
    )


# ---------------------------------------------------------------------------
# Undirected — regression
# ---------------------------------------------------------------------------

@needs_nx
def test_undirected_path_unchanged():
    G = fnx.path_graph(3)
    GX = nx.path_graph(3)
    assert list(fnx.eulerian_path(G)) == list(nx.eulerian_path(GX))


@needs_nx
def test_undirected_K4_raises_no_path():
    G = fnx.complete_graph(4)
    GX = nx.complete_graph(4)
    with pytest.raises(fnx.NetworkXError):
        list(fnx.eulerian_path(G))
    with pytest.raises(nx.NetworkXError):
        list(nx.eulerian_path(GX))
