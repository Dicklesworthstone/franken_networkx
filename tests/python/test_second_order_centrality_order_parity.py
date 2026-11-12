"""Parity for ``second_order_centrality`` dict iteration order.

Bead br-r37-c1-f6epo. fnx returned a dict in the Rust binding's
internal order (e.g. for ``path_graph(5)``: ``[2, 4, 0, 1, 3]``)
instead of nx's node-insertion order (``[0, 1, 2, 3, 4]``). Same
iteration-order drift fixed earlier in
``communicability_betweenness_centrality`` (br-r37-c1-pm78h).
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


@needs_nx
def test_path_graph_iteration_order():
    G = fnx.path_graph(5)
    GX = nx.path_graph(5)
    f = fnx.second_order_centrality(G)
    n = nx.second_order_centrality(GX)
    assert list(f.keys()) == list(n.keys()) == [0, 1, 2, 3, 4]


@needs_nx
def test_cycle_graph_iteration_order():
    G = fnx.cycle_graph(5)
    GX = nx.cycle_graph(5)
    f = fnx.second_order_centrality(G)
    n = nx.second_order_centrality(GX)
    assert list(f.keys()) == list(n.keys())


@needs_nx
def test_string_node_iteration_order():
    G = fnx.Graph()
    GX = nx.Graph()
    for u, v in [("a", "b"), ("b", "c"), ("c", "d")]:
        G.add_edge(u, v)
        GX.add_edge(u, v)
    f = fnx.second_order_centrality(G)
    n = nx.second_order_centrality(GX)
    assert list(f.keys()) == list(n.keys()) == ["a", "b", "c", "d"]


@needs_nx
def test_values_within_floating_point_noise():
    G = fnx.path_graph(5)
    GX = nx.path_graph(5)
    f = fnx.second_order_centrality(G)
    n = nx.second_order_centrality(GX)
    for k in n:
        assert abs(f[k] - n[k]) < 1e-6


@needs_nx
def test_complete_graph_keys_set_match():
    G = fnx.complete_graph(4)
    GX = nx.complete_graph(4)
    f = fnx.second_order_centrality(G)
    n = nx.second_order_centrality(GX)
    assert list(f.keys()) == list(n.keys())


@needs_nx
def test_post_add_node_order_preserved():
    """When edges are added in non-sorted order, iteration order
    follows the resulting node-insertion order."""
    G = fnx.Graph()
    GX = nx.Graph()
    G.add_edges_from([(2, 3), (1, 2), (0, 1), (3, 4)])
    GX.add_edges_from([(2, 3), (1, 2), (0, 1), (3, 4)])
    f = fnx.second_order_centrality(G)
    n = nx.second_order_centrality(GX)
    assert list(f.keys()) == list(n.keys())
