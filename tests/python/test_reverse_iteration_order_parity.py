"""Parity for ``reverse`` / ``DiGraph.reverse`` edge + adj iteration.

Bead br-r37-c1-3lqi6 / br-r37-c1-0c6wz. The Rust binding's reverse() copy traversed
internal adjacency in a different order than nx, producing a graph
whose ``edges()`` and per-node ``adj`` iteration drifted from nx.

nx's reverse(copy=True) iterates source nodes in node-insertion
order and inserts (v, u, data) edges in that traversal — so the
reversed graph's adj[v] gets u's appended in original edge-insertion
order. The Rust binding traversed in a Rust-internal order, which
silently broke any drop-in code that iterated the reversed graph's
edges/adj.

Repro:
  edges = [('a','b'),('b','c'),('c','d')]
  fnx -> [('c','b'),('d','c'),('b','a')]
  nx  -> [('b','a'),('c','b'),('d','c')]
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


def _make_dg(lib, edges):
    g = lib.DiGraph()
    for u, v in edges:
        g.add_edge(u, v)
    return g


@needs_nx
def test_path_edges_match_nx():
    edges = [("a", "b"), ("b", "c"), ("c", "d")]
    dg = _make_dg(fnx, edges)
    dgx = _make_dg(nx, edges)
    assert list(fnx.reverse(dg).edges()) == list(nx.reverse(dgx).edges())


@needs_nx
def test_cycle_edges_match_nx():
    edges = [(0, 1), (1, 2), (2, 3), (3, 0)]
    dg = _make_dg(fnx, edges)
    dgx = _make_dg(nx, edges)
    assert list(fnx.reverse(dg).edges()) == list(nx.reverse(dgx).edges())


@needs_nx
def test_repro_5edge_digraph_edges_and_adj_match_nx():
    edges = [("c", "d"), ("a", "b"), ("b", "c"), ("d", "a"), ("c", "a")]
    dg = _make_dg(fnx, edges)
    dgx = _make_dg(nx, edges)
    f_rev = fnx.reverse(dg)
    n_rev = nx.reverse(dgx)
    assert list(f_rev.edges()) == list(n_rev.edges())
    for n in n_rev.nodes():
        assert list(f_rev.adj[n]) == list(n_rev.adj[n])


@needs_nx
def test_method_form_matches_function_form_and_nx():
    """DiGraph.reverse() goes through the same wrapper."""
    edges = [("c", "d"), ("a", "b"), ("b", "c"), ("d", "a"), ("c", "a")]
    dg = _make_dg(fnx, edges)
    dgx = _make_dg(nx, edges)
    assert list(dg.reverse().edges()) == list(dgx.reverse().edges())


@needs_nx
def test_copy_false_returns_view_with_matching_edges():
    """copy=False returns a live view — already matched, sanity-only."""
    edges = [("a", "b"), ("b", "c"), ("c", "d")]
    dg = _make_dg(fnx, edges)
    dgx = _make_dg(nx, edges)
    f_view = fnx.reverse(dg, copy=False)
    n_view = nx.reverse(dgx, copy=False)
    assert list(f_view.edges()) == list(n_view.edges())


@needs_nx
def test_edge_attributes_preserved_on_copy():
    dg = fnx.DiGraph()
    dgx = nx.DiGraph()
    dg.add_edge("a", "b", weight=2.5, color="red")
    dgx.add_edge("a", "b", weight=2.5, color="red")
    assert dict(fnx.reverse(dg)["b"]["a"]) == dict(nx.reverse(dgx)["b"]["a"])


@needs_nx
def test_node_attributes_preserved_on_copy():
    dg = fnx.DiGraph()
    dgx = nx.DiGraph()
    dg.add_node("a", color="red")
    dg.add_node("b", color="blue")
    dg.add_edge("a", "b")
    dgx.add_node("a", color="red")
    dgx.add_node("b", color="blue")
    dgx.add_edge("a", "b")
    f = fnx.reverse(dg)
    n = nx.reverse(dgx)
    assert f.nodes["a"] == n.nodes["a"]
    assert f.nodes["b"] == n.nodes["b"]


@needs_nx
def test_graph_level_attrs_preserved_on_copy():
    dg = fnx.DiGraph(name="test")
    dg.graph["custom"] = 42
    dg.add_edge("a", "b")
    rev = fnx.reverse(dg)
    assert rev.graph.get("name") == "test"
    assert rev.graph.get("custom") == 42


@needs_nx
def test_multidigraph_reverse_keys_match_nx():
    edges = [("a", "b"), ("a", "b"), ("b", "c")]
    mdg = fnx.MultiDiGraph()
    mdgx = nx.MultiDiGraph()
    for u, v in edges:
        mdg.add_edge(u, v)
        mdgx.add_edge(u, v)
    assert sorted(fnx.reverse(mdg).edges(keys=True)) == sorted(
        nx.reverse(mdgx).edges(keys=True)
    )


@needs_nx
def test_undirected_input_raises_networkx_error():
    g = fnx.Graph([(0, 1)])
    with pytest.raises(fnx.NetworkXError, match="undirected"):
        fnx.reverse(g)


@needs_nx
def test_isolated_nodes_preserved():
    dg = fnx.DiGraph()
    dgx = nx.DiGraph()
    dg.add_nodes_from(["a", "b", "c"])
    dgx.add_nodes_from(["a", "b", "c"])
    dg.add_edge("a", "b")
    dgx.add_edge("a", "b")
    assert list(fnx.reverse(dg).nodes()) == list(nx.reverse(dgx).nodes())


@needs_nx
def test_empty_digraph_round_trips():
    dg = fnx.DiGraph()
    dgx = nx.DiGraph()
    f = fnx.reverse(dg)
    n = nx.reverse(dgx)
    assert f.number_of_nodes() == n.number_of_nodes() == 0
    assert f.number_of_edges() == n.number_of_edges() == 0
