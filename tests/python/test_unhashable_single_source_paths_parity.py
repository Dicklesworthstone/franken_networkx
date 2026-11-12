"""Parity for single_source_* and bidirectional_dijkstra on unhashable.

Bead br-r37-c1-ybw1s (fifth follow-up to the unhashable-node series:
br-r37-c1-m0io3 → -g438p → -i9whv → -c4agn). Six single_source_*
functions raised the wrong exception class (NodeNotFound) instead
of nx's TypeError; bidirectional_dijkstra had the OPPOSITE drift
(TypeError instead of nx's NodeNotFound).

Functions affected:
  single_source_dijkstra_path           fnx: NodeNotFound  nx: TypeError
  single_source_dijkstra_path_length    fnx: NodeNotFound  nx: TypeError
  single_source_dijkstra                fnx: NodeNotFound  nx: TypeError
  single_source_bellman_ford_path       fnx: NodeNotFound  nx: TypeError
  single_source_bellman_ford_path_length fnx: NodeNotFound  nx: TypeError
  single_source_bellman_ford            fnx: NodeNotFound  nx: TypeError
  bidirectional_dijkstra                fnx: TypeError     nx: NodeNotFound

The first six all hash-check up front. ``bidirectional_dijkstra``
needs the *opposite* fix: nx's impl uses ``source not in G``
(silent-False on unhashable, no hash op) and raises NodeNotFound;
fnx must pre-membership-check before delegating to dijkstra_path
(which now hash-validates and would raise TypeError).
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

UNHASHABLE = [
    pytest.param([1, 2], id="list"),
    pytest.param({1, 2}, id="set"),
    pytest.param({"a": 1}, id="dict"),
]

SS_FNS = [
    "single_source_dijkstra_path",
    "single_source_dijkstra_path_length",
    "single_source_dijkstra",
    "single_source_bellman_ford_path",
    "single_source_bellman_ford_path_length",
    "single_source_bellman_ford",
]


@needs_nx
@pytest.mark.parametrize("val", UNHASHABLE)
@pytest.mark.parametrize("fn_name", SS_FNS)
def test_single_source_unhashable_raises_typeerror(fn_name, val):
    G = fnx.Graph([(1, 2)])
    GX = nx.Graph([(1, 2)])
    f_fn = getattr(fnx, fn_name)
    n_fn = getattr(nx, fn_name)
    with pytest.raises(TypeError, match=r"unhashable type"):
        f_fn(G, val)
    with pytest.raises(TypeError, match=r"unhashable type"):
        n_fn(GX, val)


@needs_nx
@pytest.mark.parametrize("val", UNHASHABLE)
def test_bidirectional_dijkstra_unhashable_raises_node_not_found(val):
    """nx's bidirectional_dijkstra uses ``source not in G`` (which
    silently returns False on unhashable, no hash op) and raises
    NodeNotFound. fnx must match — pre-membership-check before
    delegating to dijkstra_path which would otherwise raise
    TypeError (after br-r37-c1-c4agn)."""
    G = fnx.Graph([(1, 2)])
    GX = nx.Graph([(1, 2)])
    with pytest.raises(fnx.NodeNotFound, match=r"Source .* is not in G"):
        fnx.bidirectional_dijkstra(G, val, 1)
    with pytest.raises(nx.NodeNotFound, match=r"Source .* is not in G"):
        nx.bidirectional_dijkstra(GX, val, 1)


@needs_nx
@pytest.mark.parametrize("val", UNHASHABLE)
def test_bidirectional_dijkstra_unhashable_target_raises_node_not_found(val):
    G = fnx.Graph([(1, 2)])
    GX = nx.Graph([(1, 2)])
    with pytest.raises(fnx.NodeNotFound):
        fnx.bidirectional_dijkstra(G, 1, val)
    with pytest.raises(nx.NodeNotFound):
        nx.bidirectional_dijkstra(GX, 1, val)


# ---------------------------------------------------------------------------
# Regression — hashable / missing inputs unaffected
# ---------------------------------------------------------------------------

@needs_nx
def test_single_source_missing_hashable_still_node_not_found():
    G = fnx.Graph([(1, 2)])
    GX = nx.Graph([(1, 2)])
    with pytest.raises(fnx.NodeNotFound):
        fnx.single_source_dijkstra_path(G, 99)
    with pytest.raises(nx.NodeNotFound):
        nx.single_source_dijkstra_path(GX, 99)


@needs_nx
def test_single_source_dijkstra_hashable_unchanged():
    G = fnx.Graph([(1, 2), (2, 3)])
    GX = nx.Graph([(1, 2), (2, 3)])
    f = fnx.single_source_dijkstra_path(G, 1)
    n = nx.single_source_dijkstra_path(GX, 1)
    assert dict(f) == dict(n)


@needs_nx
def test_bidirectional_dijkstra_hashable_unchanged():
    G = fnx.Graph([(1, 2), (2, 3), (3, 4)])
    GX = nx.Graph([(1, 2), (2, 3), (3, 4)])
    assert fnx.bidirectional_dijkstra(G, 1, 4) == nx.bidirectional_dijkstra(GX, 1, 4)
