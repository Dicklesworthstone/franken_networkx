"""Parity for ``dfs_predecessors`` / ``dfs_successors`` dict order.

Bead br-r37-c1-20swv. The Rust _dfs_predecessors_raw and
_dfs_successors_raw helpers returned dicts with keys in Rust-
internal order rather than nx's DFS-discovery order. The values
(parent for each node, list of children for each node) were
already correct — only the dict iteration order differed.

Drop-in code that iterated the dict in nx's DFS-discovery order
broke (e.g. for visualising the DFS tree, or computing per-node
metrics in algorithm order).

Repro:
  edges = [('c','d'),('a','b'),('b','c'),('d','e'),('a','c')]
  fnx.dfs_predecessors(g, 'a') -> {'d':'c','e':'d','b':'a','c':'b'}
  nx .dfs_predecessors(gx,'a') -> {'b':'a','c':'b','d':'c','e':'d'}
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


def _make_digraph(lib, edges):
    g = lib.DiGraph()
    for u, v in edges:
        g.add_edge(u, v)
    return g


@needs_nx
def test_repro_dfs_predecessors_keys_match_nx():
    edges = [("c", "d"), ("a", "b"), ("b", "c"), ("d", "e"), ("a", "c")]
    g = _make_graph(fnx, edges)
    gx = _make_graph(nx, edges)
    f = fnx.dfs_predecessors(g, "a")
    n = nx.dfs_predecessors(gx, "a")
    assert list(f.keys()) == list(n.keys())
    assert f == n


@needs_nx
def test_repro_dfs_successors_keys_match_nx():
    edges = [("c", "d"), ("a", "b"), ("b", "c"), ("d", "e"), ("a", "c")]
    g = _make_graph(fnx, edges)
    gx = _make_graph(nx, edges)
    f = fnx.dfs_successors(g, "a")
    n = nx.dfs_successors(gx, "a")
    assert list(f.keys()) == list(n.keys())
    assert f == n


@needs_nx
def test_dfs_predecessors_with_alternate_source():
    edges = [("c", "d"), ("a", "b"), ("b", "c"), ("d", "e"), ("a", "c")]
    g = _make_graph(fnx, edges)
    gx = _make_graph(nx, edges)
    assert fnx.dfs_predecessors(g, "c") == nx.dfs_predecessors(gx, "c")
    assert list(fnx.dfs_predecessors(g, "c").keys()) == list(
        nx.dfs_predecessors(gx, "c").keys()
    )


@needs_nx
def test_dfs_successors_with_alternate_source():
    edges = [("c", "d"), ("a", "b"), ("b", "c"), ("d", "e"), ("a", "c")]
    g = _make_graph(fnx, edges)
    gx = _make_graph(nx, edges)
    assert fnx.dfs_successors(g, "c") == nx.dfs_successors(gx, "c")
    assert list(fnx.dfs_successors(g, "c").keys()) == list(
        nx.dfs_successors(gx, "c").keys()
    )


@needs_nx
def test_dfs_predecessors_directed_graph_matches_nx():
    edges = [("a", "b"), ("b", "c"), ("c", "d"), ("a", "e")]
    dg = _make_digraph(fnx, edges)
    dgx = _make_digraph(nx, edges)
    assert fnx.dfs_predecessors(dg, "a") == nx.dfs_predecessors(dgx, "a")
    assert list(fnx.dfs_predecessors(dg, "a").keys()) == list(
        nx.dfs_predecessors(dgx, "a").keys()
    )


@needs_nx
def test_dfs_successors_directed_graph_matches_nx():
    edges = [("a", "b"), ("b", "c"), ("c", "d"), ("a", "e")]
    dg = _make_digraph(fnx, edges)
    dgx = _make_digraph(nx, edges)
    assert fnx.dfs_successors(dg, "a") == nx.dfs_successors(dgx, "a")
    assert list(fnx.dfs_successors(dg, "a").keys()) == list(
        nx.dfs_successors(dgx, "a").keys()
    )


@needs_nx
def test_dfs_predecessors_no_source_matches_nx():
    """No-source variant uses all nodes as roots."""
    edges = [(0, 1), (1, 2), (3, 4)]
    g = _make_graph(fnx, edges)
    gx = _make_graph(nx, edges)
    f = fnx.dfs_predecessors(g)
    n = nx.dfs_predecessors(gx)
    assert list(f.keys()) == list(n.keys())
    assert f == n


@needs_nx
def test_dfs_successors_no_source_matches_nx():
    edges = [(0, 1), (1, 2), (3, 4)]
    g = _make_graph(fnx, edges)
    gx = _make_graph(nx, edges)
    f = fnx.dfs_successors(g)
    n = nx.dfs_successors(gx)
    assert list(f.keys()) == list(n.keys())
    assert f == n


@needs_nx
def test_dfs_predecessors_with_depth_limit():
    edges = [("a", "b"), ("b", "c"), ("c", "d"), ("d", "e")]
    g = _make_graph(fnx, edges)
    gx = _make_graph(nx, edges)
    f = fnx.dfs_predecessors(g, "a", depth_limit=2)
    n = nx.dfs_predecessors(gx, "a", depth_limit=2)
    assert list(f.keys()) == list(n.keys())
    assert f == n


@needs_nx
def test_dfs_successors_with_depth_limit():
    edges = [("a", "b"), ("b", "c"), ("c", "d"), ("d", "e")]
    g = _make_graph(fnx, edges)
    gx = _make_graph(nx, edges)
    f = fnx.dfs_successors(g, "a", depth_limit=2)
    n = nx.dfs_successors(gx, "a", depth_limit=2)
    assert list(f.keys()) == list(n.keys())
    assert f == n


@needs_nx
def test_dfs_predecessors_with_sort_neighbors():
    """The sort_neighbors path was already correct; verify still works."""
    edges = [("a", "b"), ("a", "c"), ("a", "d")]
    g = _make_graph(fnx, edges)
    gx = _make_graph(nx, edges)
    sort_fn = lambda nodes: sorted(nodes, reverse=True)
    f = fnx.dfs_predecessors(g, "a", sort_neighbors=sort_fn)
    n = nx.dfs_predecessors(gx, "a", sort_neighbors=sort_fn)
    assert list(f.keys()) == list(n.keys())
    assert f == n


@needs_nx
def test_dfs_predecessors_missing_source_raises():
    g = fnx.path_graph(3)
    with pytest.raises(fnx.NetworkXError):
        fnx.dfs_predecessors(g, "missing")


@needs_nx
def test_dfs_successors_missing_source_raises():
    g = fnx.path_graph(3)
    with pytest.raises(fnx.NetworkXError):
        fnx.dfs_successors(g, "missing")


@needs_nx
def test_dfs_predecessors_empty_graph_returns_empty():
    g = fnx.Graph()
    gx = nx.Graph()
    assert fnx.dfs_predecessors(g) == nx.dfs_predecessors(gx) == {}


@needs_nx
def test_dfs_successors_empty_graph_returns_empty():
    g = fnx.Graph()
    gx = nx.Graph()
    assert fnx.dfs_successors(g) == nx.dfs_successors(gx) == {}
