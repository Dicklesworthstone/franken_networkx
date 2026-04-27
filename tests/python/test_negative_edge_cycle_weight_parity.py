"""Parity for negative_edge_cycle non-string weight argument.

Bead br-r37-c1-f0i2s.

The Rust binding exposed by ``_raw_negative_edge_cycle`` declares
``weight: str`` so passing ``weight=5`` (or ``None``, or any other
non-string) raises::

    TypeError: argument 'weight': 'int' object is not an instance of 'str'

…before the algorithm runs.  nx accepts any hashable as ``weight``
(it's used as an attribute key on edge-data dicts; non-string keys
silently fall back to the unweighted-default-of-1).

This is the same drift class as br-r37-c1-blu7u (which patched
the central dijkstra / bellman_ford / floyd_warshall / astar
delegation gates) — but ``negative_edge_cycle`` has its own gate
``_should_delegate_negative_edge_cycle_to_networkx`` that was
missed in that round.
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

NONSTRING_WEIGHTS = [
    pytest.param(5, id="int"),
    pytest.param(1.5, id="float"),
    pytest.param(b"weight", id="bytes"),
    pytest.param(("w",), id="tuple"),
    pytest.param(None, id="None"),
]


@needs_nx
@pytest.mark.parametrize("w", NONSTRING_WEIGHTS)
def test_negative_edge_cycle_undirected_nonstring_weight_matches_nx(w):
    """Undirected path: gate now routes non-string weight to nx;
    no negative cycle is found because nx falls back to default-1
    weights and the graph has positive edges."""
    G = fnx.Graph()
    G.add_weighted_edges_from([(0, 1, -1), (1, 2, 1)])
    GX = nx.Graph()
    GX.add_weighted_edges_from([(0, 1, -1), (1, 2, 1)])
    assert fnx.negative_edge_cycle(G, weight=w) == nx.negative_edge_cycle(GX, weight=w)


@needs_nx
@pytest.mark.parametrize("w", NONSTRING_WEIGHTS)
def test_negative_edge_cycle_directed_nonstring_weight_matches_nx(w):
    """Directed path: same — non-string weight delegates to nx."""
    DG = fnx.DiGraph()
    DG.add_weighted_edges_from([(0, 1, -1), (1, 2, -1), (2, 0, -1)])
    DGX = nx.DiGraph()
    DGX.add_weighted_edges_from([(0, 1, -1), (1, 2, -1), (2, 0, -1)])
    assert fnx.negative_edge_cycle(DG, weight=w) == nx.negative_edge_cycle(DGX, weight=w)


# ---------------------------------------------------------------------------
# Regressions — string and callable weights unchanged
# ---------------------------------------------------------------------------

@needs_nx
def test_negative_edge_cycle_string_weight_unchanged():
    G = fnx.Graph()
    G.add_weighted_edges_from([(0, 1, -1), (1, 2, 1)])
    GX = nx.Graph()
    GX.add_weighted_edges_from([(0, 1, -1), (1, 2, 1)])
    assert fnx.negative_edge_cycle(G, weight="weight") == nx.negative_edge_cycle(GX, weight="weight")


@needs_nx
def test_negative_edge_cycle_callable_weight_unchanged():
    G = fnx.Graph()
    G.add_weighted_edges_from([(0, 1, -1), (1, 2, 1)])
    GX = nx.Graph()
    GX.add_weighted_edges_from([(0, 1, -1), (1, 2, 1)])
    f = fnx.negative_edge_cycle(G, weight=lambda u, v, d: d.get("weight", 1.0))
    n = nx.negative_edge_cycle(GX, weight=lambda u, v, d: d.get("weight", 1.0))
    assert f == n


@needs_nx
def test_negative_edge_cycle_real_cycle_undirected_unchanged():
    """Sanity: real undirected negative-cycle graph still detected."""
    G = fnx.Graph()
    G.add_weighted_edges_from([(0, 1, -1), (1, 2, -1), (0, 2, -1)])
    GX = nx.Graph()
    GX.add_weighted_edges_from([(0, 1, -1), (1, 2, -1), (0, 2, -1)])
    assert fnx.negative_edge_cycle(G, weight="weight") == nx.negative_edge_cycle(GX, weight="weight")
