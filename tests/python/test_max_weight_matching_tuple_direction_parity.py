"""Parity for ``max_weight_matching`` tuple direction + matching choice.

Bead br-r37-c1-kpnc8. The Rust binding's matching returned each
matched pair (u, v) in a different direction than nx ((v, u) in
nx's DFS-augmenting-path traversal order), and on graphs where
multiple equally-optimal matchings exist, selected a different
valid choice from nx's adj-iteration-driven search.

Drop-in code that compared the matching against a reference set
of (u, v) pairs broke. Both libs return correct max-weight
matchings — just not the *same* matching.

Repro: edges = [(0,1),(2,3),(4,5)]
  fnx -> {(0,1), (2,3), (4,5)}
  nx  -> {(1,0), (3,2), (5,4)}   (tuple direction reversed)

Bipartite repro:
  edges = [('a','x'),('a','y'),('b','x'),('b','z'),('c','y'),('c','z')]
  fnx -> {('a','y'),('b','x'),('c','z')}
  nx  -> {('a','x'),('b','z'),('c','y')}   (different valid matching)
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


def _make_graph(lib, edges, weighted=False, weight_attr="weight"):
    g = lib.Graph()
    for ed in edges:
        if weighted:
            u, v, w = ed
            g.add_edge(u, v, **{weight_attr: w})
        else:
            g.add_edge(*ed)
    return g


@needs_nx
def test_disjoint_edges_tuple_direction_matches_nx():
    edges = [(0, 1), (2, 3), (4, 5)]
    g = _make_graph(fnx, edges)
    gx = _make_graph(nx, edges)
    assert fnx.max_weight_matching(g) == nx.max_weight_matching(gx)


@needs_nx
def test_simple_path_matching_matches_nx():
    edges = [("p", "q"), ("q", "r"), ("r", "s")]
    g = _make_graph(fnx, edges)
    gx = _make_graph(nx, edges)
    assert fnx.max_weight_matching(g) == nx.max_weight_matching(gx)


@needs_nx
def test_bipartite_repro_matching_choice_matches_nx():
    """Multiple valid maximum matchings exist; fnx must pick nx's."""
    edges = [("a", "x"), ("a", "y"), ("b", "x"), ("b", "z"), ("c", "y"), ("c", "z")]
    g = _make_graph(fnx, edges)
    gx = _make_graph(nx, edges)
    assert fnx.max_weight_matching(g) == nx.max_weight_matching(gx)


@needs_nx
def test_complete_graph_k4_matches_nx():
    g = fnx.complete_graph(4)
    gx = nx.complete_graph(4)
    assert fnx.max_weight_matching(g) == nx.max_weight_matching(gx)


@needs_nx
def test_weighted_matching_matches_nx():
    edges = [("a", "b", 2), ("b", "c", 3), ("c", "d", 1), ("a", "d", 4)]
    g = _make_graph(fnx, edges, weighted=True)
    gx = _make_graph(nx, edges, weighted=True)
    assert fnx.max_weight_matching(g) == nx.max_weight_matching(gx)


@needs_nx
def test_custom_weight_attr_matches_nx():
    edges = [("a", "b", 2), ("b", "c", 3), ("c", "d", 1), ("a", "d", 4)]
    g = _make_graph(fnx, edges, weighted=True, weight_attr="custom_w")
    gx = _make_graph(nx, edges, weighted=True, weight_attr="custom_w")
    assert fnx.max_weight_matching(g, weight="custom_w") == nx.max_weight_matching(gx, weight="custom_w")


@needs_nx
def test_maxcardinality_kwarg_matches_nx():
    g = fnx.complete_graph(5)
    gx = nx.complete_graph(5)
    assert fnx.max_weight_matching(g, maxcardinality=True) == nx.max_weight_matching(gx, maxcardinality=True)


@needs_nx
def test_empty_graph_matches_nx():
    g = fnx.Graph()
    gx = nx.Graph()
    assert fnx.max_weight_matching(g) == nx.max_weight_matching(gx) == set()


@needs_nx
def test_single_edge_matches_nx():
    g = fnx.Graph([(0, 1)])
    gx = nx.Graph([(0, 1)])
    assert fnx.max_weight_matching(g) == nx.max_weight_matching(gx)


@needs_nx
def test_min_edge_cover_internal_consumer_unchanged():
    """min_edge_cover internally calls max_weight_matching. Verify
    that the internal tuple-direction change doesn't break the cover
    contract (cover edges should still cover every vertex)."""
    edges = [("a", "x"), ("a", "y"), ("b", "x"), ("b", "z"), ("c", "y"), ("c", "z")]
    g = _make_graph(fnx, edges)
    gx = _make_graph(nx, edges)
    f = fnx.min_edge_cover(g)
    n = nx.min_edge_cover(gx)
    # Both produce a valid edge cover; on undirected, normalise to
    # frozenset edges before comparing.
    assert set(frozenset(e) for e in f) == set(frozenset(e) for e in n)


@needs_nx
def test_is_perfect_matching_consistent_after_delegation():
    """After fnx.max_weight_matching delegates, the returned matching
    must still pass fnx.is_perfect_matching on a graph where one
    exists (regression check for matching-vs-graph round-trip)."""
    g = fnx.complete_graph(4)
    m = fnx.max_weight_matching(g)
    assert fnx.is_perfect_matching(g, m)


@needs_nx
def test_bipartite_complete_k33_matches_nx():
    g = fnx.complete_bipartite_graph(3, 3)
    gx = nx.complete_bipartite_graph(3, 3)
    assert fnx.max_weight_matching(g) == nx.max_weight_matching(gx)
