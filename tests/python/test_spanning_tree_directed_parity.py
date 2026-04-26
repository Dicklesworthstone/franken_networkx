"""Parity for ``minimum_spanning_tree`` / ``maximum_spanning_tree`` on directed input.

Bead br-r37-c1-ow5fy. fnx silently returned a Graph result for
``minimum_spanning_tree(DiGraph)`` and ``maximum_spanning_tree(DiGraph)``;
nx raises ``NetworkXNotImplemented('not implemented for directed
type')``. MST is undefined on directed graphs (use
``minimum_spanning_arborescence``). Drop-in code that catches
NotImplemented to fall back to arborescence broke.

``minimum_spanning_edges`` and ``maximum_spanning_edges`` already
correctly rejected directed; only the tree variants needed the guard.
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
# Directed: must raise NetworkXNotImplemented
# ---------------------------------------------------------------------------

@needs_nx
def test_minimum_spanning_tree_on_digraph_raises_not_implemented():
    DG = fnx.DiGraph([(0, 1), (1, 2)])
    DGX = nx.DiGraph([(0, 1), (1, 2)])
    with pytest.raises(fnx.NetworkXNotImplemented) as fnx_exc:
        fnx.minimum_spanning_tree(DG)
    with pytest.raises(nx.NetworkXNotImplemented) as nx_exc:
        nx.minimum_spanning_tree(DGX)
    assert str(fnx_exc.value) == str(nx_exc.value) == "not implemented for directed type"


@needs_nx
def test_maximum_spanning_tree_on_digraph_raises_not_implemented():
    DG = fnx.DiGraph([(0, 1), (1, 2)])
    DGX = nx.DiGraph([(0, 1), (1, 2)])
    with pytest.raises(fnx.NetworkXNotImplemented) as fnx_exc:
        fnx.maximum_spanning_tree(DG)
    with pytest.raises(nx.NetworkXNotImplemented) as nx_exc:
        nx.maximum_spanning_tree(DGX)
    assert str(fnx_exc.value) == str(nx_exc.value)


@needs_nx
def test_minimum_spanning_tree_on_multidigraph_raises_not_implemented():
    MDG = fnx.MultiDiGraph([(0, 1)])
    MDGX = nx.MultiDiGraph([(0, 1)])
    with pytest.raises(fnx.NetworkXNotImplemented):
        fnx.minimum_spanning_tree(MDG)
    with pytest.raises(nx.NetworkXNotImplemented):
        nx.minimum_spanning_tree(MDGX)


# ---------------------------------------------------------------------------
# Undirected — regression
# ---------------------------------------------------------------------------

@needs_nx
def test_minimum_spanning_tree_undirected_unchanged():
    G = fnx.cycle_graph(5)
    GX = nx.cycle_graph(5)
    for u, v, k in [(0, 1, 1), (1, 2, 5), (2, 3, 2), (3, 4, 3), (4, 0, 4)]:
        G[u][v]["weight"] = k
        GX[u][v]["weight"] = k
    assert sorted(fnx.minimum_spanning_tree(G).edges(data=True)) == sorted(
        nx.minimum_spanning_tree(GX).edges(data=True)
    )


@needs_nx
def test_maximum_spanning_tree_undirected_unchanged():
    G = fnx.cycle_graph(5)
    GX = nx.cycle_graph(5)
    for u, v, k in [(0, 1, 1), (1, 2, 5), (2, 3, 2), (3, 4, 3), (4, 0, 4)]:
        G[u][v]["weight"] = k
        GX[u][v]["weight"] = k
    assert sorted(fnx.maximum_spanning_tree(G).edges(data=True)) == sorted(
        nx.maximum_spanning_tree(GX).edges(data=True)
    )


# ---------------------------------------------------------------------------
# Drop-in: NotImplemented can be caught to fall back to arborescence
# ---------------------------------------------------------------------------

@needs_nx
def test_drop_in_not_implemented_catch_fallback_to_arborescence():
    """Verify the typical drop-in pattern works: catch NotImplemented
    and fall back to the directed arborescence variant."""
    DG = fnx.DiGraph([(0, 1), (1, 2)])
    try:
        result = fnx.minimum_spanning_tree(DG)
        used_arborescence = False
    except fnx.NetworkXNotImplemented:
        result = fnx.minimum_spanning_arborescence(DG)
        used_arborescence = True
    assert used_arborescence
    assert result.is_directed()
