"""Parity for ``_fnx_to_nx`` converter adjacency-iteration order.

Bead br-r37-c1-sgnab. The converter previously iterated ``fg.edges``
(canonical-endpoint form) which fed nx's ``add_edge`` calls in the
wrong order: nx stores adj[u] in user-call insertion order, so
calling ``add_edge('c', 'b')`` puts 'c' first in adj[b] but the
user originally called ``add_edge('b', 'c')`` putting 'a' first
(after a prior ``add_edge('a', 'b')`` call).

This silently broke any delegated algorithm whose result depends on
adj iteration: BFS/DFS-strategy greedy_color, ego_graph traversal,
etc.

Fix uses a per-node-queue topological emit so the converter calls
add_edge in an order that preserves each node's adj-insertion
sequence.
"""

from __future__ import annotations

import pytest

import franken_networkx as fnx

try:
    import networkx as nx
    HAS_NX = True
except ImportError:
    HAS_NX = False

from franken_networkx.backend import _fnx_to_nx

needs_nx = pytest.mark.skipif(not HAS_NX, reason="networkx not installed")


@needs_nx
def test_simple_graph_adj_order_preserved():
    """The motivating case: edges added with mixed direction."""
    g = fnx.Graph()
    gx = nx.Graph()
    for u, v in [("c", "d"), ("a", "b"), ("b", "c"), ("d", "e")]:
        g.add_edge(u, v)
        gx.add_edge(u, v)

    converted = _fnx_to_nx(g)
    for n in gx.nodes():
        assert list(converted.adj[n]) == list(gx.adj[n]), (
            f"adj[{n}]: converted={list(converted.adj[n])} "
            f"direct-nx={list(gx.adj[n])}"
        )


@needs_nx
def test_path_graph_adj_order_preserved():
    g = fnx.path_graph(5)
    gx = nx.path_graph(5)
    converted = _fnx_to_nx(g)
    for n in gx.nodes():
        assert list(converted.adj[n]) == list(gx.adj[n])


@needs_nx
def test_self_loop_preserved():
    """Regression: self-loops shouldn't drop other edges."""
    g = fnx.Graph()
    g.add_edge(0, 0)
    g.add_edge(0, 1)
    converted = _fnx_to_nx(g)
    assert sorted(converted.edges()) == [(0, 0), (0, 1)]


@needs_nx
def test_self_loop_with_multiple_neighbors():
    g = fnx.Graph()
    g.add_edge(0, 1)
    g.add_edge(0, 0)
    g.add_edge(0, 2)
    converted = _fnx_to_nx(g)
    assert (0, 0) in converted.edges()
    assert (0, 1) in converted.edges() or (1, 0) in converted.edges()
    assert (0, 2) in converted.edges() or (2, 0) in converted.edges()


@needs_nx
def test_grid_graph_tuple_nodes():
    """Tuple-node graphs (grid_graph) should round-trip without
    dropping edges."""
    g = fnx.grid_graph([2, 2])
    gx = nx.grid_graph([2, 2])
    converted = _fnx_to_nx(g)
    assert sorted(converted.edges()) == sorted(gx.edges())


@needs_nx
def test_directed_graph_preserves_out_edge_order():
    g = fnx.DiGraph()
    gx = nx.DiGraph()
    for u, v in [(2, 3), (0, 1), (1, 2), (3, 4)]:
        g.add_edge(u, v)
        gx.add_edge(u, v)
    converted = _fnx_to_nx(g)
    for n in gx.nodes():
        assert list(converted.adj[n]) == list(gx.adj[n])


@needs_nx
def test_disconnected_components_adj_preserved():
    g = fnx.Graph()
    gx = nx.Graph()
    for u, v in [("a", "b"), ("c", "d"), ("e", "f")]:
        g.add_edge(u, v)
        gx.add_edge(u, v)
    converted = _fnx_to_nx(g)
    for n in gx.nodes():
        assert list(converted.adj[n]) == list(gx.adj[n])


@needs_nx
def test_empty_graph_round_trips():
    g = fnx.Graph()
    converted = _fnx_to_nx(g)
    assert converted.number_of_nodes() == 0
    assert converted.number_of_edges() == 0


@needs_nx
def test_graph_with_attrs_preserves_attrs_and_adj_order():
    g = fnx.Graph()
    gx = nx.Graph()
    g.add_edge("a", "b", weight=2.5)
    gx.add_edge("a", "b", weight=2.5)
    g.add_edge("b", "c", weight=1.0)
    gx.add_edge("b", "c", weight=1.0)
    converted = _fnx_to_nx(g)
    for n in gx.nodes():
        assert list(converted.adj[n]) == list(gx.adj[n])
    assert converted["a"]["b"] == gx["a"]["b"]
    assert converted["b"]["c"] == gx["b"]["c"]


@needs_nx
def test_multiple_self_loops_on_same_node():
    g = fnx.Graph()
    g.add_edge(0, 0)
    g.add_edge(0, 1)
    g.add_edge(0, 2)
    g.add_edge(0, 3)
    converted = _fnx_to_nx(g)
    edges = sorted(converted.edges())
    assert (0, 0) in edges
    assert (0, 1) in edges
    assert (0, 2) in edges
    assert (0, 3) in edges
