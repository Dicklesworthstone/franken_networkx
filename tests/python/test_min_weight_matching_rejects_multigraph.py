"""br-r37-c1-gt95l: regression tests for min_weight_matching guard parity.

Sister of br-r37-c1-mwm-mg (which fixed max_weight_matching).
nx's min_weight_matching rejects directed + multigraph via
not_implemented_for decorators; the fnx wrapper previously
silently projected MultiGraph to simple Graph — a convenience that
masked nx's contract.
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


def test_min_weight_matching_rejects_multigraph():
    g = fnx.MultiGraph()
    g.add_edge(0, 1, weight=1.0)
    g.add_edge(1, 2, weight=2.0)
    with pytest.raises(fnx.NetworkXNotImplemented, match="multigraph"):
        fnx.min_weight_matching(g)


def test_min_weight_matching_rejects_directed():
    g = fnx.DiGraph()
    g.add_edge(0, 1, weight=1.0)
    with pytest.raises(fnx.NetworkXNotImplemented, match="directed"):
        fnx.min_weight_matching(g)


def test_min_weight_matching_rejects_multidigraph():
    g = fnx.MultiDiGraph()
    g.add_edge(0, 1, weight=1.0)
    # nx's decorator order: directed first, multigraph second; mirror that.
    with pytest.raises(fnx.NetworkXNotImplemented):
        fnx.min_weight_matching(g)


@needs_nx
def test_min_weight_matching_undirected_simple_matches_nx():
    edges = [(0, 1, 2.0), (1, 2, 1.0), (2, 3, 3.0)]
    fg = fnx.Graph()
    ng = nx.Graph()
    for u, v, w in edges:
        fg.add_edge(u, v, weight=w)
        ng.add_edge(u, v, weight=w)
    fr = fnx.min_weight_matching(fg)
    nr = nx.min_weight_matching(ng)
    # nx returns a set of 2-tuples; the exact tuple direction may differ
    # historically (br-r37-c1-fs3bl notes this), but after the fix the
    # wrapper delegates entirely so the tuples should match exactly.
    assert fr == nr
