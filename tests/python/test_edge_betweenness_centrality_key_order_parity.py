"""Parity for ``edge_betweenness_centrality`` dict key order + direction.

Bead br-r37-c1-pi615. The Rust _raw_edge_betweenness_centrality
returned the result dict with keys in canonical (smaller-first)
edge order, but nx returns keys in G.edges() iteration order with
edge tuples in the discovered traversal direction (e.g. ('c','b')
not ('b','c')).

Repro:
  edges = [('c','d'),('a','b'),('b','c'),('d','e'),('a','c')]
  fnx (pre-fix) -> {('a','b'): 0.1, ('a','c'): 0.3,  ('b','c'): 0.3,  ('c','d'): 0.6, ('d','e'): 0.4}
  nx            -> {('c','d'): 0.6, ('c','b'): 0.3,  ('c','a'): 0.3,  ('d','e'): 0.4, ('a','b'): 0.1}

Values match; only dict key shape and ordering differ. Fix re-keys
the Rust output by walking G.edges() once and looking up the value
in either tuple direction.
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


def _make_graph(lib, edges):
    g = lib.Graph()
    for u, v in edges:
        g.add_edge(u, v)
    return g


@needs_nx
def test_repro_str_node_keys_match_nx():
    edges = [("c", "d"), ("a", "b"), ("b", "c"), ("d", "e"), ("a", "c")]
    g = _make_graph(fnx, edges)
    gx = _make_graph(nx, edges)
    f = fnx.edge_betweenness_centrality(g)
    n = nx.edge_betweenness_centrality(gx)
    assert list(f.keys()) == list(n.keys())
    assert f == n


@needs_nx
def test_int_node_path_matches_nx():
    g = fnx.path_graph(5)
    gx = nx.path_graph(5)
    f = fnx.edge_betweenness_centrality(g)
    n = nx.edge_betweenness_centrality(gx)
    assert list(f.keys()) == list(n.keys())
    assert f == n


@needs_nx
def test_triangle_with_pendant_matches_nx():
    edges = [(0, 1), (0, 2), (1, 2), (2, 3), (3, 4), (4, 2)]
    g = _make_graph(fnx, edges)
    gx = _make_graph(nx, edges)
    f = fnx.edge_betweenness_centrality(g)
    n = nx.edge_betweenness_centrality(gx)
    assert list(f.keys()) == list(n.keys())
    assert f == n


@needs_nx
def test_directed_graph_matches_nx():
    dg = fnx.DiGraph()
    dgx = nx.DiGraph()
    for u, v in [("a", "b"), ("b", "c"), ("c", "a"), ("a", "d")]:
        dg.add_edge(u, v)
        dgx.add_edge(u, v)
    f = fnx.edge_betweenness_centrality(dg)
    n = nx.edge_betweenness_centrality(dgx)
    assert list(f.keys()) == list(n.keys())
    assert f == n


@needs_nx
def test_weighted_delegates_to_nx():
    """weight= triggers the existing nx delegation path."""
    g = fnx.Graph()
    gx = nx.Graph()
    for u, v, w in [("a", "b", 1), ("b", "c", 2), ("c", "a", 1), ("c", "d", 1)]:
        g.add_edge(u, v, weight=w)
        gx.add_edge(u, v, weight=w)
    f = fnx.edge_betweenness_centrality(g, weight="weight")
    n = nx.edge_betweenness_centrality(gx, weight="weight")
    assert list(f.keys()) == list(n.keys())
    assert f == n


@needs_nx
def test_normalized_false_delegates_to_nx():
    """normalized=False triggers the existing nx delegation path."""
    edges = [("c", "d"), ("a", "b"), ("b", "c"), ("d", "e"), ("a", "c")]
    g = _make_graph(fnx, edges)
    gx = _make_graph(nx, edges)
    f = fnx.edge_betweenness_centrality(g, normalized=False)
    n = nx.edge_betweenness_centrality(gx, normalized=False)
    assert list(f.keys()) == list(n.keys())
    assert f == n


@needs_nx
def test_complete_graph_matches_nx():
    g = fnx.complete_graph(4)
    gx = nx.complete_graph(4)
    f = fnx.edge_betweenness_centrality(g)
    n = nx.edge_betweenness_centrality(gx)
    assert list(f.keys()) == list(n.keys())
    assert f == n


@needs_nx
def test_repro_specific_tuple_directions():
    """Exact regression on the specific tuple directions in the
    repro: nx returns ('c','b') not ('b','c'), ('c','a') not ('a','c')."""
    edges = [("c", "d"), ("a", "b"), ("b", "c"), ("d", "e"), ("a", "c")]
    g = _make_graph(fnx, edges)
    f = fnx.edge_betweenness_centrality(g)
    keys = list(f.keys())
    assert keys == [("c", "d"), ("c", "b"), ("c", "a"), ("d", "e"), ("a", "b")]


@needs_nx
def test_empty_graph_matches_nx():
    g = fnx.Graph()
    gx = nx.Graph()
    assert fnx.edge_betweenness_centrality(g) == nx.edge_betweenness_centrality(gx) == {}


@needs_nx
def test_single_edge_matches_nx():
    g = fnx.Graph([("a", "b")])
    gx = nx.Graph([("a", "b")])
    assert fnx.edge_betweenness_centrality(g) == nx.edge_betweenness_centrality(gx)
