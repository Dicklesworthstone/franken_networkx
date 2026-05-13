"""br-r37-c1-hdhe3: regression tests for is_dominating_set on directed."""

from __future__ import annotations

import pytest

import franken_networkx as fnx

try:
    import networkx as nx

    HAS_NX = True
except ImportError:
    HAS_NX = False


needs_nx = pytest.mark.skipif(not HAS_NX, reason="networkx not installed")


@needs_nx
@pytest.mark.parametrize(
    "cls_fnx,cls_nx",
    [(fnx.DiGraph, nx.DiGraph), (fnx.MultiDiGraph, nx.MultiDiGraph)],
)
def test_is_dominating_set_directed_matches_nx(cls_fnx, cls_nx):
    g = cls_fnx()
    gx = cls_nx()
    for u, v in [(0, 1), (1, 2)]:
        g.add_edge(u, v)
        gx.add_edge(u, v)
    # Node 0 dominates 0 and 1 (out-neighbor); 2 is uncovered.
    assert fnx.is_dominating_set(g, {0}) == nx.is_dominating_set(gx, {0})


@needs_nx
def test_is_dominating_set_directed_full_set_dominates():
    g = fnx.DiGraph()
    gx = nx.DiGraph()
    for u, v in [(0, 1), (1, 2)]:
        g.add_edge(u, v)
        gx.add_edge(u, v)
    full = {0, 1, 2}
    assert fnx.is_dominating_set(g, full) == nx.is_dominating_set(gx, full)


def test_is_dominating_set_undirected_unchanged():
    g = fnx.path_graph(3)
    assert fnx.is_dominating_set(g, {1}) is True  # center node dominates all
    assert fnx.is_dominating_set(g, {0}) is False  # endpoint misses node 2
