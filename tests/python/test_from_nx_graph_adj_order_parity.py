"""Parity for ``_from_nx_graph`` adj-order preservation.

Bead br-r37-c1-4d97w. nx.G.edges() canonicalises each edge to a
discovery-order direction that doesn't match nx's per-node adj
insertion order. The previous _from_nx_graph implementation walked
edges() and fed them to add_edges_from, producing an fnx graph
whose adj[u] was in edge-traversal order instead of nx's
add_edge insertion order.

Inverse problem of br-r37-c1-sgnab (_fnx_to_nx adj order). Same
fix: route through the per-node-queue topological emit helper
that already powers _fnx_to_nx.

Repro (les_miserables_graph delegates via _from_nx_graph):
  nx.les_miserables_graph().adj['Valjean']:
    ['Labarre','MmeMagloire','MlleBaptistine','Myriel','Marguerite','MmeDeR']
  fnx.les_miserables_graph().adj['Valjean'] (pre-fix):
    ['Myriel','MlleBaptistine','MmeMagloire','Labarre','Marguerite','MmeDeR']
"""

from __future__ import annotations

import pytest

import franken_networkx as fnx

try:
    import networkx as nx
    HAS_NX = True
except ImportError:
    HAS_NX = False

from franken_networkx.readwrite import _from_nx_graph

needs_nx = pytest.mark.skipif(not HAS_NX, reason="networkx not installed")


@needs_nx
def test_les_miserables_valjean_adj_matches_nx():
    f = fnx.les_miserables_graph()
    n = nx.les_miserables_graph()
    assert list(f.adj["Valjean"]) == list(n.adj["Valjean"])


@needs_nx
def test_les_miserables_full_adj_matches_nx():
    f = fnx.les_miserables_graph()
    n = nx.les_miserables_graph()
    for node in n.nodes():
        assert list(f.adj[node]) == list(n.adj[node]), f"adj[{node}] drifts"


@needs_nx
def test_les_miserables_node_and_edge_order_match_nx():
    f = fnx.les_miserables_graph()
    n = nx.les_miserables_graph()
    assert list(f.nodes()) == list(n.nodes())
    assert list(f.edges()) == list(n.edges())


@needs_nx
def test_synthetic_str_node_round_trip_adj_order_preserved():
    """Build an nx graph manually with mixed-direction add_edge, then
    convert via _from_nx_graph and verify adj order is preserved."""
    nxg = nx.Graph()
    for u, v in [("c", "d"), ("a", "b"), ("b", "c"), ("d", "e"), ("a", "c")]:
        nxg.add_edge(u, v)
    converted = _from_nx_graph(nxg)
    for node in nxg.nodes():
        assert list(converted.adj[node]) == list(nxg.adj[node]), (
            f"adj[{node}]: converted={list(converted.adj[node])} "
            f"nx={list(nxg.adj[node])}"
        )


@needs_nx
def test_synthetic_int_node_round_trip_adj_order_preserved():
    nxg = nx.Graph()
    for u, v in [(2, 3), (0, 1), (1, 2), (3, 4), (0, 2)]:
        nxg.add_edge(u, v)
    converted = _from_nx_graph(nxg)
    for node in nxg.nodes():
        assert list(converted.adj[node]) == list(nxg.adj[node])


@needs_nx
def test_directed_graph_adj_order_preserved():
    nxg = nx.DiGraph()
    for u, v in [("c", "d"), ("a", "b"), ("b", "c"), ("d", "a"), ("c", "a")]:
        nxg.add_edge(u, v)
    converted = _from_nx_graph(nxg)
    for node in nxg.nodes():
        assert list(converted.adj[node]) == list(nxg.adj[node])


@needs_nx
def test_self_loop_preserved():
    nxg = nx.Graph()
    nxg.add_edge(0, 0)
    nxg.add_edge(0, 1)
    nxg.add_edge(0, 2)
    converted = _from_nx_graph(nxg)
    for node in nxg.nodes():
        assert list(converted.adj[node]) == list(nxg.adj[node])


@needs_nx
def test_edge_attrs_preserved():
    nxg = nx.Graph()
    nxg.add_edge("a", "b", weight=2.5)
    nxg.add_edge("b", "c", weight=1.0)
    converted = _from_nx_graph(nxg)
    assert dict(converted["a"]["b"]) == dict(nxg["a"]["b"])
    assert dict(converted["b"]["c"]) == dict(nxg["b"]["c"])


@needs_nx
def test_node_attrs_preserved():
    nxg = nx.Graph()
    nxg.add_node("a", color="red")
    nxg.add_node("b", color="blue")
    nxg.add_edge("a", "b")
    converted = _from_nx_graph(nxg)
    assert converted.nodes["a"] == nxg.nodes["a"]
    assert converted.nodes["b"] == nxg.nodes["b"]


@needs_nx
def test_graph_level_attrs_preserved():
    nxg = nx.Graph(name="test")
    nxg.graph["custom"] = 42
    nxg.add_edge("a", "b")
    converted = _from_nx_graph(nxg)
    assert converted.graph.get("name") == "test"
    assert converted.graph.get("custom") == 42


@needs_nx
def test_empty_graph_round_trips():
    nxg = nx.Graph()
    converted = _from_nx_graph(nxg)
    assert converted.number_of_nodes() == 0
    assert converted.number_of_edges() == 0


@needs_nx
def test_multigraph_path_unchanged():
    """MultiGraph branch keeps the edges(keys=True, data=True) path."""
    nxg = nx.MultiGraph()
    nxg.add_edge("a", "b", key=0)
    nxg.add_edge("a", "b", key=1)
    nxg.add_edge("b", "c", key=0)
    converted = _from_nx_graph(nxg)
    assert sorted(converted.edges(keys=True)) == sorted(nxg.edges(keys=True))


@needs_nx
def test_bfs_order_after_conversion_matches_nx():
    """Downstream consequence: BFS visits in adj order, so converted
    graph's BFS must match nx's BFS exactly after the fix."""
    nxg = nx.les_miserables_graph()
    converted = _from_nx_graph(nxg)
    assert list(fnx.bfs_edges(converted, "Valjean")) == list(
        nx.bfs_edges(nxg, "Valjean")
    )
