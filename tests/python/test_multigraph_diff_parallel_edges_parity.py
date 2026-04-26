"""Parity for MultiGraph ``difference`` / ``symmetric_difference``
preservation of parallel edges.

Bead br-r37-c1-6sgls. The Rust _raw_difference and
_raw_symmetric_difference paths collapsed parallel edges to a
simple-graph difference, dropping edges that should appear in the
result. nx's MultiGraph contract treats each (u, v, key) as
distinct. Drop-in code that expected parallel edges in the result
broke.

Repro:
  mg1 edges (keys=True): [(a,b,0),(a,b,1),(b,c,0)]
  mg2 edges (keys=True): [(a,b,0),(c,d,0)]

  fnx.difference (pre-fix) -> [(b,c,0)]               <- DROPS (a,b,1)
  nx .difference           -> [(a,b,1),(b,c,0)]

  fnx.symmetric_difference (pre-fix)
                           -> [(b,c,0),(c,d,0)]       <- DROPS (a,b,1)
  nx .symmetric_difference -> [(a,b,1),(b,c,0),(c,d,0)]
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


def _build_mg_pair(edges_g, edges_h):
    """Build (fnx, nx) MultiGraph pair with synced node sets."""
    fg = fnx.MultiGraph()
    fh = fnx.MultiGraph()
    ng = nx.MultiGraph()
    nh = nx.MultiGraph()
    for u, v in edges_g:
        fg.add_edge(u, v)
        ng.add_edge(u, v)
    for u, v in edges_h:
        fh.add_edge(u, v)
        nh.add_edge(u, v)
    all_nodes = list(dict.fromkeys(list(fg.nodes()) + list(fh.nodes())))
    for n in all_nodes:
        if n not in fg:
            fg.add_node(n)
            ng.add_node(n)
        if n not in fh:
            fh.add_node(n)
            nh.add_node(n)
    return fg, fh, ng, nh


# ----- difference -----

@needs_nx
def test_repro_multigraph_difference_preserves_parallel_edges():
    fg, fh, ng, nh = _build_mg_pair(
        [("a", "b"), ("a", "b"), ("b", "c")],
        [("a", "b"), ("c", "d")],
    )
    f_result = list(fnx.difference(fg, fh).edges(keys=True))
    n_result = list(nx.difference(ng, nh).edges(keys=True))
    assert sorted(f_result) == sorted(n_result)


@needs_nx
def test_multigraph_difference_returns_multigraph():
    fg = fnx.MultiGraph([("a", "b")])
    fh = fnx.MultiGraph([("a", "b")])
    result = fnx.difference(fg, fh)
    assert isinstance(result, fnx.MultiGraph)


@needs_nx
def test_multigraph_difference_no_overlap_keeps_all():
    fg, fh, ng, nh = _build_mg_pair(
        [("a", "b"), ("a", "b")],
        [("c", "d")],
    )
    f_edges = sorted(fnx.difference(fg, fh).edges(keys=True))
    n_edges = sorted(nx.difference(ng, nh).edges(keys=True))
    assert f_edges == n_edges


@needs_nx
def test_multigraph_difference_full_overlap_returns_empty():
    fg, fh, ng, nh = _build_mg_pair(
        [("a", "b"), ("a", "b"), ("b", "c")],
        [("a", "b"), ("a", "b"), ("b", "c")],
    )
    f_edges = list(fnx.difference(fg, fh).edges(keys=True))
    n_edges = list(nx.difference(ng, nh).edges(keys=True))
    assert f_edges == n_edges == []


# ----- symmetric_difference -----

@needs_nx
def test_repro_multigraph_symmetric_difference_preserves_parallels():
    fg, fh, ng, nh = _build_mg_pair(
        [("a", "b"), ("a", "b"), ("b", "c")],
        [("a", "b"), ("c", "d")],
    )
    f_result = list(fnx.symmetric_difference(fg, fh).edges(keys=True))
    n_result = list(nx.symmetric_difference(ng, nh).edges(keys=True))
    assert sorted(f_result) == sorted(n_result)


@needs_nx
def test_multigraph_symmetric_difference_returns_multigraph():
    fg = fnx.MultiGraph([("a", "b")])
    fh = fnx.MultiGraph([("a", "b")])
    result = fnx.symmetric_difference(fg, fh)
    assert isinstance(result, fnx.MultiGraph)


@needs_nx
def test_multigraph_symmetric_difference_disjoint_full_union():
    fg, fh, ng, nh = _build_mg_pair(
        [("a", "b"), ("a", "b")],
        [("c", "d"), ("c", "d")],
    )
    f_edges = sorted(fnx.symmetric_difference(fg, fh).edges(keys=True))
    n_edges = sorted(nx.symmetric_difference(ng, nh).edges(keys=True))
    assert f_edges == n_edges


# ----- simple-graph difference / symmetric_difference unchanged -----

@needs_nx
def test_simple_graph_difference_unchanged():
    """The simple-graph difference path was already correct
    (matched nx); verify we didn't regress it with the multigraph
    fix."""
    fg = fnx.Graph([(0, 1), (1, 2), (2, 3)])
    fh = fnx.Graph([(0, 1), (2, 3)])
    fg.add_nodes_from(set(fg.nodes()) | set(fh.nodes()))
    fh.add_nodes_from(set(fg.nodes()) | set(fh.nodes()))
    ng = nx.Graph([(0, 1), (1, 2), (2, 3)])
    nh = nx.Graph([(0, 1), (2, 3)])
    ng.add_nodes_from(set(ng.nodes()) | set(nh.nodes()))
    nh.add_nodes_from(set(ng.nodes()) | set(nh.nodes()))
    assert list(fnx.difference(fg, fh).edges()) == list(nx.difference(ng, nh).edges())


@needs_nx
def test_simple_graph_symmetric_difference_unchanged():
    fg = fnx.Graph([(0, 1), (1, 2), (2, 3)])
    fh = fnx.Graph([(0, 1), (2, 3)])
    fg.add_nodes_from(set(fg.nodes()) | set(fh.nodes()))
    fh.add_nodes_from(set(fg.nodes()) | set(fh.nodes()))
    ng = nx.Graph([(0, 1), (1, 2), (2, 3)])
    nh = nx.Graph([(0, 1), (2, 3)])
    ng.add_nodes_from(set(ng.nodes()) | set(nh.nodes()))
    nh.add_nodes_from(set(ng.nodes()) | set(nh.nodes()))
    assert list(fnx.symmetric_difference(fg, fh).edges()) == list(
        nx.symmetric_difference(ng, nh).edges()
    )


# ----- node-set check still raises -----

@needs_nx
def test_difference_unequal_node_sets_raises():
    fg = fnx.MultiGraph([(0, 1)])
    fh = fnx.MultiGraph([(2, 3)])
    with pytest.raises(fnx.NetworkXError, match="Node sets"):
        fnx.difference(fg, fh)


@needs_nx
def test_symmetric_difference_unequal_node_sets_raises():
    fg = fnx.MultiGraph([(0, 1)])
    fh = fnx.MultiGraph([(2, 3)])
    with pytest.raises(fnx.NetworkXError, match="Node sets"):
        fnx.symmetric_difference(fg, fh)


# ----- multidigraph variants -----

@needs_nx
def test_multidigraph_difference_preserves_parallel_directed_edges():
    fg = fnx.MultiDiGraph()
    fh = fnx.MultiDiGraph()
    ng = nx.MultiDiGraph()
    nh = nx.MultiDiGraph()
    for u, v in [("a", "b"), ("a", "b"), ("b", "c")]:
        fg.add_edge(u, v)
        ng.add_edge(u, v)
    for u, v in [("a", "b"), ("c", "d")]:
        fh.add_edge(u, v)
        nh.add_edge(u, v)
    all_nodes = list(dict.fromkeys(list(fg.nodes()) + list(fh.nodes())))
    for n in all_nodes:
        if n not in fg:
            fg.add_node(n)
            ng.add_node(n)
        if n not in fh:
            fh.add_node(n)
            nh.add_node(n)
    f_edges = sorted(fnx.difference(fg, fh).edges(keys=True))
    n_edges = sorted(nx.difference(ng, nh).edges(keys=True))
    assert f_edges == n_edges
