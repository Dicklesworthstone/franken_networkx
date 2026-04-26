"""Parity for ``core_number`` dict iteration order.

Bead br-r37-c1-9fa26. fnx returned a dict with keys sorted (e.g. for
edges added in (2,3),(0,1),(1,2),(3,4) order: ``[0, 1, 2, 3, 4]``)
regardless of node-insertion order. nx returns the dict in node-
insertion order (``[2, 3, 0, 1, 4]``). Same iteration-order family
fixed earlier in ``communicability_betweenness_centrality``
(br-r37-c1-pm78h) and ``second_order_centrality`` (br-r37-c1-f6epo).
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
def test_core_number_iterates_in_node_insertion_order():
    """When edges are added in non-monotonic order, iteration follows
    node insertion order, not sorted-key order."""
    G = fnx.Graph()
    GX = nx.Graph()
    for u, v in [(2, 3), (0, 1), (1, 2), (3, 4)]:
        G.add_edge(u, v)
        GX.add_edge(u, v)
    f = fnx.core_number(G)
    n = nx.core_number(GX)
    assert list(f.keys()) == list(n.keys()) == [2, 3, 0, 1, 4]


@needs_nx
def test_core_number_path_graph_unchanged():
    """Path graph has natural sorted insertion order — must still match."""
    G = fnx.path_graph(5)
    GX = nx.path_graph(5)
    f = fnx.core_number(G)
    n = nx.core_number(GX)
    assert list(f.keys()) == list(n.keys()) == [0, 1, 2, 3, 4]


@needs_nx
def test_core_number_string_nodes():
    G = fnx.Graph()
    GX = nx.Graph()
    for u, v in [("c", "d"), ("a", "b"), ("b", "c")]:
        G.add_edge(u, v)
        GX.add_edge(u, v)
    f = fnx.core_number(G)
    n = nx.core_number(GX)
    assert list(f.keys()) == list(n.keys()) == ["c", "d", "a", "b"]


@needs_nx
def test_core_number_complete_graph():
    G = fnx.complete_graph(5)
    GX = nx.complete_graph(5)
    f = fnx.core_number(G)
    n = nx.core_number(GX)
    assert list(f.keys()) == list(n.keys())
    # All nodes in K5 have core number 4.
    assert all(v == 4 for v in f.values())


@needs_nx
def test_core_number_values_match_networkx():
    """Sanity: values still correct after reorder."""
    G = fnx.complete_graph(4)
    GX = nx.complete_graph(4)
    assert dict(fnx.core_number(G)) == dict(nx.core_number(GX))


@needs_nx
def test_core_number_isolated_nodes():
    """Isolated nodes get core number 0; iteration includes them."""
    G = fnx.Graph()
    GX = nx.Graph()
    G.add_nodes_from([0, 1, 2])
    GX.add_nodes_from([0, 1, 2])
    f = fnx.core_number(G)
    n = nx.core_number(GX)
    assert list(f.keys()) == list(n.keys())
    assert all(v == 0 for v in f.values())
