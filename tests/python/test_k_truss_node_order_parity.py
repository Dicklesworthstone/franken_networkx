"""Parity for ``k_truss`` subgraph nodes/edges/adj iteration.

Bead br-r37-c1-3qopf. The Rust k_truss_rust helper returned nodes
in canonical/sort order, but nx iterates them in input-graph node
order. Drop-in code that iterated R.nodes() / R.edges() / R.adj of
the k-truss subgraph in nx's order broke.

Repro:
  edges = [('c','d'),('a','b'),('b','c'),('d','e'),('a','c')]
  fnx.k_truss(g, 2).nodes() -> ['a','b','c','d','e']
  nx.k_truss(gx, 2).nodes()  -> ['c','d','a','b','e']
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
def test_repro_str_node_k2_matches_nx():
    edges = [("c", "d"), ("a", "b"), ("b", "c"), ("d", "e"), ("a", "c")]
    g = _make_graph(fnx, edges)
    gx = _make_graph(nx, edges)
    f = fnx.k_truss(g, 2)
    n = nx.k_truss(gx, 2)
    assert list(f.nodes()) == list(n.nodes())
    assert list(f.edges()) == list(n.edges())


@needs_nx
def test_int_node_k3_triangle_chain_matches_nx():
    edges = [(0, 1), (0, 2), (1, 2), (2, 3), (3, 4), (4, 2)]
    g = _make_graph(fnx, edges)
    gx = _make_graph(nx, edges)
    f = fnx.k_truss(g, 3)
    n = nx.k_truss(gx, 3)
    assert list(f.nodes()) == list(n.nodes())
    assert list(f.edges()) == list(n.edges())


@needs_nx
def test_triangle_with_pendant_matches_nx():
    edges = [("a", "b"), ("b", "c"), ("c", "a"), ("c", "d")]
    g = _make_graph(fnx, edges)
    gx = _make_graph(nx, edges)
    f = fnx.k_truss(g, 2)
    n = nx.k_truss(gx, 2)
    assert list(f.nodes()) == list(n.nodes())
    assert list(f.edges()) == list(n.edges())


@needs_nx
def test_complete_graph_k4_returns_full():
    g = fnx.complete_graph(5)
    gx = nx.complete_graph(5)
    f = fnx.k_truss(g, 4)
    n = nx.k_truss(gx, 4)
    assert list(f.nodes()) == list(n.nodes())
    assert list(f.edges()) == list(n.edges())


@needs_nx
def test_no_truss_returns_empty():
    g = fnx.path_graph(4)
    gx = nx.path_graph(4)
    f = fnx.k_truss(g, 3)
    n = nx.k_truss(gx, 3)
    assert list(f.nodes()) == list(n.nodes())
    assert list(f.edges()) == list(n.edges())


@needs_nx
def test_returns_undirected_graph():
    g = _make_graph(fnx, [("a", "b"), ("b", "c"), ("c", "a")])
    f = fnx.k_truss(g, 2)
    assert isinstance(f, fnx.Graph)


@needs_nx
def test_directed_input_raises():
    dg = fnx.DiGraph([(0, 1)])
    with pytest.raises(fnx.NetworkXNotImplemented, match="directed"):
        fnx.k_truss(dg, 2)


@needs_nx
def test_multigraph_input_raises():
    mg = fnx.MultiGraph([(0, 1), (0, 1)])
    with pytest.raises(fnx.NetworkXNotImplemented, match="multigraph"):
        fnx.k_truss(mg, 2)


@needs_nx
@pytest.mark.parametrize("k", [0, 1, 2, 3])
def test_self_loop_rejection_matches_nx_exactly(k):
    edges = [("a", "a"), ("a", "b"), ("b", "c")]
    g = _make_graph(fnx, edges)
    gx = _make_graph(nx, edges)

    with pytest.raises(nx.NetworkXNotImplemented) as nx_error:
        nx.k_truss(gx, k)
    with pytest.raises(fnx.NetworkXNotImplemented) as fnx_error:
        fnx.k_truss(g, k)

    assert str(fnx_error.value) == str(nx_error.value)


@needs_nx
@pytest.mark.parametrize("k", [0, 1])
def test_edgeless_graph_drops_isolates_at_low_k(k):
    g = fnx.Graph(campaign="parity")
    gx = nx.Graph(campaign="parity")
    g.add_nodes_from([("a", {"rank": 1}), ("b", {"rank": 2}), "c"])
    gx.add_nodes_from([("a", {"rank": 1}), ("b", {"rank": 2}), "c"])

    f = fnx.k_truss(g, k)
    n = nx.k_truss(gx, k)

    assert list(f.nodes(data=True)) == list(n.nodes(data=True)) == []
    assert list(f.edges(data=True)) == list(n.edges(data=True)) == []
    assert dict(f.graph) == dict(n.graph) == {"campaign": "parity"}


@needs_nx
@pytest.mark.parametrize("k", [0, 1, 2])
def test_low_k_drops_input_isolates_but_preserves_survivor_attrs(k):
    g = fnx.Graph(campaign="parity")
    gx = nx.Graph(campaign="parity")
    for graph in (g, gx):
        graph.add_node("a", rank=1)
        graph.add_node("b", rank=2)
        graph.add_node("isolated", rank=3)
        graph.add_edge("a", "b", weight=7)

    f = fnx.k_truss(g, k)
    n = nx.k_truss(gx, k)

    assert list(f.nodes(data=True)) == list(n.nodes(data=True))
    assert list(f.edges(data=True)) == list(n.edges(data=True))
    assert dict(f.graph) == dict(n.graph)


@needs_nx
def test_repro_specific_node_order_regression():
    """Regression: nx returns ['c','d','a','b','e'] for the repro case."""
    edges = [("c", "d"), ("a", "b"), ("b", "c"), ("d", "e"), ("a", "c")]
    g = _make_graph(fnx, edges)
    f = fnx.k_truss(g, 2)
    assert list(f.nodes()) == ["c", "d", "a", "b", "e"]


@needs_nx
def test_adj_order_matches_nx():
    edges = [("c", "d"), ("a", "b"), ("b", "c"), ("d", "e"), ("a", "c")]
    g = _make_graph(fnx, edges)
    gx = _make_graph(nx, edges)
    f = fnx.k_truss(g, 2)
    n = nx.k_truss(gx, 2)
    for node in n.nodes():
        assert list(f.adj[node]) == list(n.adj[node])
