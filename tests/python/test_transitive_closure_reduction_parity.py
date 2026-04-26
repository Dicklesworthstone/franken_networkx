"""Parity for ``transitive_reduction`` and ``transitive_closure_dag``.

Bead br-r37-c1-utmy6. Both functions used the Rust binding which
produced output graphs whose edge() and adj iteration order
drifted from nx.

Repro:
  edges = [('a','b'),('a','c'),('b','d'),('c','d'),('d','e')]
  fnx.transitive_reduction(dag).edges() ->
    [('a','c'),('a','b'),('b','d'),('c','d'),('d','e')]
  nx.transitive_reduction(dagx).edges()  ->
    [('a','b'),('a','c'),('b','d'),('c','d'),('d','e')]

Drop-in code that iterated ``R.edges()`` or ``adj[node]`` of either
output silently broke. Fix delegates both to nx so output graph
iteration order matches nx's contract.
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


def _make_dag(lib, edges):
    g = lib.DiGraph()
    for u, v in edges:
        g.add_edge(u, v)
    return g


# ----- transitive_reduction -----

@needs_nx
def test_repro_diamond_dag_edges_match_nx():
    edges = [("a", "b"), ("a", "c"), ("b", "d"), ("c", "d"), ("d", "e")]
    dag = _make_dag(fnx, edges)
    dagx = _make_dag(nx, edges)
    assert list(fnx.transitive_reduction(dag).edges()) == list(
        nx.transitive_reduction(dagx).edges()
    )


@needs_nx
def test_redundant_edge_removed_matches_nx():
    """A direct edge a->c is redundant when a->b->c exists."""
    edges = [("a", "b"), ("b", "c"), ("a", "c")]
    dag = _make_dag(fnx, edges)
    dagx = _make_dag(nx, edges)
    f = fnx.transitive_reduction(dag)
    n = nx.transitive_reduction(dagx)
    assert list(f.edges()) == list(n.edges())


@needs_nx
def test_transitive_reduction_path_unchanged():
    """A path is already its own TR."""
    edges = [("a", "b"), ("b", "c"), ("c", "d")]
    dag = _make_dag(fnx, edges)
    dagx = _make_dag(nx, edges)
    f = fnx.transitive_reduction(dag)
    n = nx.transitive_reduction(dagx)
    assert list(f.edges()) == list(n.edges())


@needs_nx
def test_transitive_reduction_returns_digraph():
    edges = [("a", "b"), ("b", "c")]
    dag = _make_dag(fnx, edges)
    f = fnx.transitive_reduction(dag)
    assert isinstance(f, fnx.DiGraph)


@needs_nx
def test_transitive_reduction_undirected_raises():
    g = fnx.Graph([(0, 1)])
    with pytest.raises(fnx.NetworkXNotImplemented, match="undirected"):
        fnx.transitive_reduction(g)


@needs_nx
def test_transitive_reduction_cycle_raises():
    """Non-DAG raises NetworkXError."""
    dg = fnx.DiGraph([(0, 1), (1, 0)])
    with pytest.raises(fnx.NetworkXError, match="Directed Acyclic Graph"):
        fnx.transitive_reduction(dg)


@needs_nx
def test_transitive_reduction_adj_matches_nx():
    edges = [("a", "b"), ("a", "c"), ("b", "d"), ("c", "d"), ("d", "e")]
    dag = _make_dag(fnx, edges)
    dagx = _make_dag(nx, edges)
    f = fnx.transitive_reduction(dag)
    n = nx.transitive_reduction(dagx)
    for nn in n.nodes():
        assert list(f.adj[nn]) == list(n.adj[nn])


# ----- transitive_closure_dag -----

@needs_nx
def test_tc_dag_repro_diamond_edges_match_nx():
    edges = [("a", "b"), ("a", "c"), ("b", "d"), ("c", "d"), ("d", "e")]
    dag = _make_dag(fnx, edges)
    dagx = _make_dag(nx, edges)
    f = fnx.transitive_closure_dag(dag)
    n = nx.transitive_closure_dag(dagx)
    assert list(f.edges()) == list(n.edges())


@needs_nx
def test_tc_dag_adj_matches_nx():
    edges = [("a", "b"), ("a", "c"), ("b", "d"), ("c", "d"), ("d", "e")]
    dag = _make_dag(fnx, edges)
    dagx = _make_dag(nx, edges)
    f = fnx.transitive_closure_dag(dag)
    n = nx.transitive_closure_dag(dagx)
    for nn in n.nodes():
        assert list(f.adj[nn]) == list(n.adj[nn])


@needs_nx
def test_tc_dag_path_matches_nx():
    edges = [(0, 1), (1, 2), (2, 3)]
    dag = _make_dag(fnx, edges)
    dagx = _make_dag(nx, edges)
    f = fnx.transitive_closure_dag(dag)
    n = nx.transitive_closure_dag(dagx)
    assert list(f.edges()) == list(n.edges())


@needs_nx
def test_tc_dag_with_topo_order_matches_nx():
    edges = [("a", "b"), ("a", "c"), ("b", "d")]
    dag = _make_dag(fnx, edges)
    dagx = _make_dag(nx, edges)
    topo = ["a", "b", "c", "d"]
    f = fnx.transitive_closure_dag(dag, topo_order=topo)
    n = nx.transitive_closure_dag(dagx, topo_order=topo)
    assert list(f.edges()) == list(n.edges())


@needs_nx
def test_tc_dag_undirected_raises():
    g = fnx.Graph([(0, 1)])
    with pytest.raises(fnx.NetworkXNotImplemented, match="undirected"):
        fnx.transitive_closure_dag(g)


@needs_nx
def test_tc_dag_returns_digraph():
    dag = _make_dag(fnx, [("a", "b"), ("b", "c")])
    f = fnx.transitive_closure_dag(dag)
    assert isinstance(f, fnx.DiGraph)


@needs_nx
def test_tc_dag_empty_graph():
    dag = fnx.DiGraph()
    dagx = nx.DiGraph()
    f = fnx.transitive_closure_dag(dag)
    n = nx.transitive_closure_dag(dagx)
    assert list(f.edges()) == list(n.edges()) == []


@needs_nx
def test_tc_dag_single_edge():
    dag = _make_dag(fnx, [("a", "b")])
    dagx = _make_dag(nx, [("a", "b")])
    f = fnx.transitive_closure_dag(dag)
    n = nx.transitive_closure_dag(dagx)
    assert list(f.edges()) == list(n.edges())
