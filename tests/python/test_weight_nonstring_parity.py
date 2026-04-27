"""Parity for non-string ``weight`` arguments on shortest-path /
eccentricity / floyd-warshall / astar functions.

Bead br-r37-c1-blu7u.

nx accepts any hashable as ``weight`` — it's used as an attribute
key on edge-data dicts, and non-string keys silently fall back to
the unweighted-default-of-1.  fnx's PyO3 bindings declare
``weight: str``, so passing ``weight=5`` (or any other non-string)
raises ``TypeError("argument 'weight': 'int' object is not an
instance of 'str'")`` BEFORE the algorithm runs — breaking
drop-in parity with nx.

Fix: the central delegation gates (``_should_delegate_dijkstra_to_
networkx`` etc.) now route non-string, non-callable, non-None
weight values through nx, where they're handled correctly.
``eccentricity``, which has its own fast-path, also delegates
non-string weights to nx.
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
]


# ---------------------------------------------------------------------------
# Path fns — non-string weights silently fall back to unweighted
# ---------------------------------------------------------------------------

@needs_nx
@pytest.mark.parametrize("w", NONSTRING_WEIGHTS)
def test_dijkstra_path_nonstring_weight_matches_nx(w):
    G = fnx.Graph([(1, 2), (2, 3)])
    GX = nx.Graph([(1, 2), (2, 3)])
    f = fnx.dijkstra_path(G, 1, 3, weight=w)
    n = nx.dijkstra_path(GX, 1, 3, weight=w)
    assert f == n


@needs_nx
@pytest.mark.parametrize("w", NONSTRING_WEIGHTS)
def test_dijkstra_path_length_nonstring_weight_matches_nx(w):
    G = fnx.Graph([(1, 2), (2, 3)])
    GX = nx.Graph([(1, 2), (2, 3)])
    f = fnx.dijkstra_path_length(G, 1, 3, weight=w)
    n = nx.dijkstra_path_length(GX, 1, 3, weight=w)
    assert f == n


@needs_nx
@pytest.mark.parametrize("w", NONSTRING_WEIGHTS)
def test_bellman_ford_path_nonstring_weight_matches_nx(w):
    G = fnx.Graph([(1, 2), (2, 3)])
    GX = nx.Graph([(1, 2), (2, 3)])
    f = fnx.bellman_ford_path(G, 1, 3, weight=w)
    n = nx.bellman_ford_path(GX, 1, 3, weight=w)
    assert f == n


@needs_nx
@pytest.mark.parametrize("w", NONSTRING_WEIGHTS)
def test_astar_path_nonstring_weight_matches_nx(w):
    G = fnx.Graph([(1, 2), (2, 3)])
    GX = nx.Graph([(1, 2), (2, 3)])
    f = fnx.astar_path(G, 1, 3, weight=w)
    n = nx.astar_path(GX, 1, 3, weight=w)
    assert f == n


@needs_nx
@pytest.mark.parametrize("w", NONSTRING_WEIGHTS)
def test_shortest_path_nonstring_weight_matches_nx(w):
    G = fnx.Graph([(1, 2), (2, 3)])
    GX = nx.Graph([(1, 2), (2, 3)])
    f = fnx.shortest_path(G, 1, 3, weight=w)
    n = nx.shortest_path(GX, 1, 3, weight=w)
    assert f == n


@needs_nx
@pytest.mark.parametrize("w", NONSTRING_WEIGHTS)
def test_eccentricity_nonstring_weight_matches_nx(w):
    G = fnx.Graph([(1, 2), (2, 3)])
    GX = nx.Graph([(1, 2), (2, 3)])
    f = fnx.eccentricity(G, weight=w)
    n = nx.eccentricity(GX, weight=w)
    assert dict(f) == dict(n)


@needs_nx
@pytest.mark.parametrize("w", NONSTRING_WEIGHTS)
def test_johnson_nonstring_weight_matches_nx(w):
    G = fnx.Graph([(1, 2), (2, 3)])
    GX = nx.Graph([(1, 2), (2, 3)])
    f = fnx.johnson(G, weight=w)
    n = nx.johnson(GX, weight=w)
    assert {k: dict(v) for k, v in f.items()} == {k: dict(v) for k, v in n.items()}


# ---------------------------------------------------------------------------
# Regressions — string weights and None unaffected
# ---------------------------------------------------------------------------

@needs_nx
def test_dijkstra_path_string_weight_unchanged():
    G = fnx.Graph()
    G.add_weighted_edges_from([(1, 2, 1.0), (2, 3, 2.0), (1, 3, 5.0)])
    GX = nx.Graph()
    GX.add_weighted_edges_from([(1, 2, 1.0), (2, 3, 2.0), (1, 3, 5.0)])
    assert fnx.dijkstra_path(G, 1, 3, weight="weight") == nx.dijkstra_path(GX, 1, 3, weight="weight")


@needs_nx
def test_dijkstra_path_none_weight_unchanged():
    G = fnx.Graph([(1, 2), (2, 3)])
    GX = nx.Graph([(1, 2), (2, 3)])
    assert fnx.dijkstra_path(G, 1, 3, weight=None) == nx.dijkstra_path(GX, 1, 3, weight=None)


@needs_nx
def test_dijkstra_path_callable_weight_unchanged():
    G = fnx.Graph([(1, 2), (2, 3)])
    GX = nx.Graph([(1, 2), (2, 3)])
    f = fnx.dijkstra_path(G, 1, 3, weight=lambda u, v, d: 1.0)
    n = nx.dijkstra_path(GX, 1, 3, weight=lambda u, v, d: 1.0)
    assert f == n
