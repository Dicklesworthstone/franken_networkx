"""Parity for ``node_degree_xy`` iterator order.

Bead br-r37-c1-6yimw. nx iterates ``xdeg(set(nodes))`` which yields
nodes in hash-set order (since the implementation calls
``set(G)`` and iterates that). The previous fnx loop walked
``present_nodes`` in G.nodes()-insertion order, producing the same
multiset of (degree_x, degree_y) pairs but in a different sequence.

Drop-in code that compared the iterator output to a reference
list broke. Fix replicates nx's exact algorithm.

Repro:
  edges = [(c,d),(a,b),(b,c),(d,e),(a,c)]
  fnx (pre-fix) -> [(3,2),(3,2),(3,2),(2,3),(2,1),(2,2),(2,3),(2,2),(2,3),(1,2)]
  nx            -> [(2,2),(2,3),(2,3),(2,1),(2,2),(2,3),(1,2),(3,2),(3,2),(3,2)]
  (Sorted: identical.)
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
def test_repro_str_node_iter_matches_nx():
    edges = [("c", "d"), ("a", "b"), ("b", "c"), ("d", "e"), ("a", "c")]
    g = _make_graph(fnx, edges)
    gx = _make_graph(nx, edges)
    assert list(fnx.node_degree_xy(g)) == list(nx.node_degree_xy(gx))


@needs_nx
def test_int_node_path_matches_nx():
    g = fnx.path_graph(5)
    gx = nx.path_graph(5)
    assert list(fnx.node_degree_xy(g)) == list(nx.node_degree_xy(gx))


@needs_nx
def test_complete_graph_matches_nx():
    g = fnx.complete_graph(4)
    gx = nx.complete_graph(4)
    assert list(fnx.node_degree_xy(g)) == list(nx.node_degree_xy(gx))


@needs_nx
def test_directed_graph_x_out_y_in_matches_nx():
    edges = [("a", "b"), ("b", "c"), ("c", "a"), ("a", "d")]
    dg = fnx.DiGraph()
    dgx = nx.DiGraph()
    for u, v in edges:
        dg.add_edge(u, v)
        dgx.add_edge(u, v)
    assert list(fnx.node_degree_xy(dg, x="out", y="in")) == list(
        nx.node_degree_xy(dgx, x="out", y="in")
    )


@needs_nx
def test_directed_graph_x_in_y_out_matches_nx():
    edges = [("a", "b"), ("b", "c"), ("c", "a"), ("a", "d")]
    dg = fnx.DiGraph()
    dgx = nx.DiGraph()
    for u, v in edges:
        dg.add_edge(u, v)
        dgx.add_edge(u, v)
    assert list(fnx.node_degree_xy(dg, x="in", y="out")) == list(
        nx.node_degree_xy(dgx, x="in", y="out")
    )


@needs_nx
def test_with_nodes_kwarg_matches_nx():
    edges = [("c", "d"), ("a", "b"), ("b", "c"), ("d", "e"), ("a", "c")]
    g = _make_graph(fnx, edges)
    gx = _make_graph(nx, edges)
    assert list(fnx.node_degree_xy(g, nodes=["a", "b", "c"])) == list(
        nx.node_degree_xy(gx, nodes=["a", "b", "c"])
    )


@needs_nx
def test_with_weight_matches_nx():
    g = fnx.Graph()
    gx = nx.Graph()
    for u, v, w in [("a", "b", 1), ("b", "c", 2), ("c", "a", 3)]:
        g.add_edge(u, v, weight=w)
        gx.add_edge(u, v, weight=w)
    assert list(fnx.node_degree_xy(g, weight="weight")) == list(
        nx.node_degree_xy(gx, weight="weight")
    )


@needs_nx
def test_multigraph_yields_per_parallel_edge():
    """MultiGraph: each (u, v, key) parallel edge should produce
    its own (degree, degree) tuple."""
    mg = fnx.MultiGraph([("a", "b"), ("a", "b"), ("b", "c"), ("c", "a")])
    mgx = nx.MultiGraph([("a", "b"), ("a", "b"), ("b", "c"), ("c", "a")])
    f = list(fnx.node_degree_xy(mg))
    n = list(nx.node_degree_xy(mgx))
    # Sorted match (parallel edges produce identical tuples that
    # appear multiple times) — verify count and multiset.
    assert sorted(f) == sorted(n)


@needs_nx
def test_multigraph_iter_order_matches_nx():
    mg = fnx.MultiGraph([("a", "b"), ("a", "b"), ("b", "c"), ("c", "a")])
    mgx = nx.MultiGraph([("a", "b"), ("a", "b"), ("b", "c"), ("c", "a")])
    assert list(fnx.node_degree_xy(mg)) == list(nx.node_degree_xy(mgx))


@needs_nx
def test_empty_graph_yields_empty():
    g = fnx.Graph()
    gx = nx.Graph()
    assert list(fnx.node_degree_xy(g)) == list(nx.node_degree_xy(gx)) == []


@needs_nx
def test_isolated_nodes_no_edges_no_tuples():
    g = fnx.Graph()
    g.add_nodes_from([0, 1, 2])
    gx = nx.Graph()
    gx.add_nodes_from([0, 1, 2])
    assert list(fnx.node_degree_xy(g)) == list(nx.node_degree_xy(gx)) == []


@needs_nx
def test_self_loops_treated_as_one_edge():
    g = fnx.Graph([(0, 0), (0, 1)])
    gx = nx.Graph([(0, 0), (0, 1)])
    assert list(fnx.node_degree_xy(g)) == list(nx.node_degree_xy(gx))


@needs_nx
def test_multiset_of_tuples_matches_nx():
    """Even before the fix, the multiset of tuples matched —
    sanity-check that property is preserved."""
    edges = [("c", "d"), ("a", "b"), ("b", "c"), ("d", "e"), ("a", "c")]
    g = _make_graph(fnx, edges)
    gx = _make_graph(nx, edges)
    assert sorted(fnx.node_degree_xy(g)) == sorted(nx.node_degree_xy(gx))
