"""Parity for ``minimum_node_cut`` / ``minimum_edge_cut`` cut choice.

Bead br-r37-c1-5jbv9. Both cuts are correct in size, but on graphs
where multiple equally-small cuts exist, the Rust binding (for
node cut) and the local Python implementation (for edge cut)
picked a different valid cut from nx — the choice depends on
internal adj-iteration / DFS-augmenting-path traversal.

Drop-in code that compared the cut against a reference set
silently broke. Fix delegates both to nx so the chosen cut and
edge tuple direction match nx's traversal contract exactly.

Repro:
  edges = [('c','d'),('a','b'),('b','c'),('d','e'),('a','c')]
  nx.minimum_edge_cut -> {('d','c')}
  fnx (pre-fix)      -> {('d','e')}
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


# ----- minimum_node_cut -----

@needs_nx
def test_min_node_cut_str_node_repro_matches_nx():
    edges = [("c", "d"), ("a", "b"), ("b", "c"), ("d", "e"), ("a", "c")]
    g = _make_graph(fnx, edges)
    gx = _make_graph(nx, edges)
    assert fnx.minimum_node_cut(g) == nx.minimum_node_cut(gx)


@needs_nx
def test_min_node_cut_path_matches_nx():
    g = fnx.path_graph(5)
    gx = nx.path_graph(5)
    assert fnx.minimum_node_cut(g) == nx.minimum_node_cut(gx)


@needs_nx
def test_min_node_cut_diamond_matches_nx():
    edges = [(0, 1), (0, 2), (1, 3), (2, 3)]
    g = _make_graph(fnx, edges)
    gx = _make_graph(nx, edges)
    assert fnx.minimum_node_cut(g) == nx.minimum_node_cut(gx)


@needs_nx
def test_min_node_cut_with_s_t_matches_nx():
    edges = [("s", "a"), ("s", "b"), ("a", "t"), ("b", "t"), ("a", "b")]
    g = _make_graph(fnx, edges)
    gx = _make_graph(nx, edges)
    assert fnx.minimum_node_cut(g, s="s", t="t") == nx.minimum_node_cut(gx, s="s", t="t")


@needs_nx
def test_min_node_cut_returns_set():
    """nx contract: return type is set."""
    g = fnx.path_graph(5)
    cut = fnx.minimum_node_cut(g)
    assert isinstance(cut, set)


@needs_nx
def test_min_node_cut_complete_graph_matches_nx():
    """K_n's minimum node cut is n-1 nodes (any (n-1) of the n)."""
    g = fnx.complete_graph(4)
    gx = nx.complete_graph(4)
    assert fnx.minimum_node_cut(g) == nx.minimum_node_cut(gx)


# ----- minimum_edge_cut -----

@needs_nx
def test_min_edge_cut_str_node_repro_matches_nx():
    edges = [("c", "d"), ("a", "b"), ("b", "c"), ("d", "e"), ("a", "c")]
    g = _make_graph(fnx, edges)
    gx = _make_graph(nx, edges)
    assert fnx.minimum_edge_cut(g) == nx.minimum_edge_cut(gx)


@needs_nx
def test_min_edge_cut_path_matches_nx():
    g = fnx.path_graph(5)
    gx = nx.path_graph(5)
    assert fnx.minimum_edge_cut(g) == nx.minimum_edge_cut(gx)


@needs_nx
def test_min_edge_cut_diamond_matches_nx():
    edges = [(0, 1), (0, 2), (1, 3), (2, 3)]
    g = _make_graph(fnx, edges)
    gx = _make_graph(nx, edges)
    assert fnx.minimum_edge_cut(g) == nx.minimum_edge_cut(gx)


@needs_nx
def test_min_edge_cut_with_s_t_matches_nx():
    edges = [("s", "a"), ("s", "b"), ("a", "t"), ("b", "t"), ("a", "b")]
    g = _make_graph(fnx, edges)
    gx = _make_graph(nx, edges)
    assert fnx.minimum_edge_cut(g, s="s", t="t") == nx.minimum_edge_cut(gx, s="s", t="t")


@needs_nx
def test_min_edge_cut_complete_graph_size_n_minus_1():
    """K_n's edge cut is n-1 edges; both libs agree on the choice."""
    g = fnx.complete_graph(4)
    gx = nx.complete_graph(4)
    f = fnx.minimum_edge_cut(g)
    n = nx.minimum_edge_cut(gx)
    assert f == n
    assert len(f) == 3


@needs_nx
def test_min_edge_cut_returns_set():
    """nx contract: return type is set."""
    g = fnx.path_graph(5)
    cut = fnx.minimum_edge_cut(g)
    assert isinstance(cut, set)


@needs_nx
def test_min_edge_cut_directed_graph_matches_nx():
    """DiGraph case — direction matters for the cut tuple."""
    dg = fnx.DiGraph()
    dgx = nx.DiGraph()
    for u, v in [("s", "a"), ("a", "b"), ("b", "t"), ("s", "b"), ("a", "t")]:
        dg.add_edge(u, v)
        dgx.add_edge(u, v)
    assert fnx.minimum_edge_cut(dg, s="s", t="t") == nx.minimum_edge_cut(dgx, s="s", t="t")


# ----- correctness regression -----

@needs_nx
def test_min_edge_cut_size_is_correct():
    """Even after the choice changes, the cut still has minimum size."""
    edges = [("c", "d"), ("a", "b"), ("b", "c"), ("d", "e"), ("a", "c")]
    g = _make_graph(fnx, edges)
    gx = _make_graph(nx, edges)
    f = fnx.minimum_edge_cut(g)
    assert len(f) == nx.edge_connectivity(gx)


@needs_nx
def test_min_node_cut_size_is_correct():
    """Even after the choice changes, the cut still has minimum size."""
    edges = [("c", "d"), ("a", "b"), ("b", "c"), ("d", "e"), ("a", "c")]
    g = _make_graph(fnx, edges)
    gx = _make_graph(nx, edges)
    f = fnx.minimum_node_cut(g)
    assert len(f) == nx.node_connectivity(gx)
