"""Parity for ``generic_bfs_edges`` default-neighbors path.

Bead br-r37-c1-lnqss. The Rust _fnx.generic_bfs_edges_rust default
path (when ``neighbors`` is None) yielded edges with adj iteration
in a different order than nx. The plain bfs_edges variant matched
nx; only generic_bfs_edges via the Rust default-neighbors branch
drifted.

Repro:
  edges = [(c,d),(a,b),(b,c),(d,e),(a,c)]
  Both libs: adj[a] = [b, c]

  fnx.generic_bfs_edges(g, source='a') -> [(a,c),(a,b),(c,d),(d,e)]
  nx .generic_bfs_edges(gx, source='a') -> [(a,b),(a,c),(c,d),(d,e)]

  When neighbors=g.neighbors is passed explicitly, the Python path
  matched nx exactly.
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
def test_repro_str_node_default_neighbors_matches_nx():
    edges = [("c", "d"), ("a", "b"), ("b", "c"), ("d", "e"), ("a", "c")]
    g = _make_graph(fnx, edges)
    gx = _make_graph(nx, edges)
    assert list(fnx.generic_bfs_edges(g, source="a")) == list(
        nx.generic_bfs_edges(gx, source="a")
    )


@needs_nx
def test_int_node_path_matches_nx():
    g = fnx.path_graph(5)
    gx = nx.path_graph(5)
    assert list(fnx.generic_bfs_edges(g, source=0)) == list(
        nx.generic_bfs_edges(gx, source=0)
    )


@needs_nx
def test_complete_graph_matches_nx():
    g = fnx.complete_graph(4)
    gx = nx.complete_graph(4)
    assert list(fnx.generic_bfs_edges(g, source=0)) == list(
        nx.generic_bfs_edges(gx, source=0)
    )


@needs_nx
def test_with_depth_limit_matches_nx():
    edges = [("c", "d"), ("a", "b"), ("b", "c"), ("d", "e"), ("a", "c")]
    g = _make_graph(fnx, edges)
    gx = _make_graph(nx, edges)
    assert list(fnx.generic_bfs_edges(g, source="a", depth_limit=2)) == list(
        nx.generic_bfs_edges(gx, source="a", depth_limit=2)
    )


@needs_nx
def test_with_explicit_neighbors_callback_matches_nx():
    """The callback path was already correct; verify still works."""
    edges = [("c", "d"), ("a", "b"), ("b", "c"), ("d", "e"), ("a", "c")]
    g = _make_graph(fnx, edges)
    gx = _make_graph(nx, edges)
    assert list(fnx.generic_bfs_edges(g, source="a", neighbors=g.neighbors)) == list(
        nx.generic_bfs_edges(gx, source="a", neighbors=gx.neighbors)
    )


@needs_nx
def test_directed_graph_default_neighbors_matches_nx():
    dg = fnx.DiGraph()
    dgx = nx.DiGraph()
    for u, v in [("a", "b"), ("b", "c"), ("a", "c"), ("c", "d")]:
        dg.add_edge(u, v)
        dgx.add_edge(u, v)
    assert list(fnx.generic_bfs_edges(dg, source="a")) == list(
        nx.generic_bfs_edges(dgx, source="a")
    )


@needs_nx
def test_isolated_source_matches_nx():
    g = fnx.Graph()
    g.add_node("a")
    gx = nx.Graph()
    gx.add_node("a")
    assert list(fnx.generic_bfs_edges(g, source="a")) == list(
        nx.generic_bfs_edges(gx, source="a")
    )


@needs_nx
def test_disconnected_graph_only_visits_source_component_matches_nx():
    edges = [("a", "b"), ("b", "c"), ("d", "e")]
    g = _make_graph(fnx, edges)
    gx = _make_graph(nx, edges)
    assert list(fnx.generic_bfs_edges(g, source="a")) == list(
        nx.generic_bfs_edges(gx, source="a")
    )


@needs_nx
def test_specific_repro_edge_order_regression():
    """Specific regression: nx yields (a,b),(a,c) in that order."""
    edges = [("c", "d"), ("a", "b"), ("b", "c"), ("d", "e"), ("a", "c")]
    g = _make_graph(fnx, edges)
    result = list(fnx.generic_bfs_edges(g, source="a"))
    assert result[0] == ("a", "b")
    assert result[1] == ("a", "c")


@needs_nx
def test_depth_limit_zero_yields_nothing():
    g = fnx.path_graph(5)
    gx = nx.path_graph(5)
    assert list(fnx.generic_bfs_edges(g, source=0, depth_limit=0)) == list(
        nx.generic_bfs_edges(gx, source=0, depth_limit=0)
    ) == []
