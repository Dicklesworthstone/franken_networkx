"""Parity for ``triangles`` dict iteration order.

Bead br-r37-c1-k3khk. fnx returned a dict with keys sorted; nx
iterates in node-insertion order. Same iteration-order family fixed
in br-r37-c1-pm78h (communicability_betweenness_centrality),
br-r37-c1-f6epo (second_order_centrality), and br-r37-c1-9fa26
(core_number).
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
def test_triangles_iterates_in_insertion_order():
    """When edges are added in non-monotonic order, iteration follows
    node insertion order, not sorted-key order."""
    G = fnx.Graph()
    GX = nx.Graph()
    for u, v in [(2, 3), (0, 1), (1, 2), (3, 4)]:
        G.add_edge(u, v)
        GX.add_edge(u, v)
    f = fnx.triangles(G)
    n = nx.triangles(GX)
    assert list(f.keys()) == list(n.keys()) == [2, 3, 0, 1, 4]


@needs_nx
def test_triangles_string_nodes_iteration_order():
    G = fnx.Graph()
    GX = nx.Graph()
    for u, v in [("c", "d"), ("a", "b"), ("b", "c")]:
        G.add_edge(u, v)
        GX.add_edge(u, v)
    f = fnx.triangles(G)
    n = nx.triangles(GX)
    assert list(f.keys()) == list(n.keys()) == ["c", "d", "a", "b"]


@needs_nx
def test_triangles_k4_values_unchanged():
    """Sanity: values still correct after reorder."""
    G = fnx.complete_graph(4)
    GX = nx.complete_graph(4)
    assert dict(fnx.triangles(G)) == dict(nx.triangles(GX))
    assert all(v == 3 for v in fnx.triangles(G).values())


@needs_nx
def test_triangles_empty_graph():
    G = fnx.Graph()
    GX = nx.Graph()
    assert dict(fnx.triangles(G)) == dict(nx.triangles(GX)) == {}


@needs_nx
def test_triangles_isolated_nodes_iteration():
    """Isolated nodes (degree 0) should still appear in iteration."""
    G = fnx.Graph()
    GX = nx.Graph()
    G.add_nodes_from([2, 0, 1])
    GX.add_nodes_from([2, 0, 1])
    G.add_edge(0, 1)
    GX.add_edge(0, 1)
    f = fnx.triangles(G)
    n = nx.triangles(GX)
    assert list(f.keys()) == list(n.keys())
    assert all(v == 0 for v in f.values())


@needs_nx
def test_triangles_with_nodes_kwarg_subset():
    """Subset selection via nodes= kwarg returns dict in iteration
    order of the subset (same on both libs)."""
    G = fnx.cycle_graph(5)
    GX = nx.cycle_graph(5)
    f = fnx.triangles(G, nodes=[2, 0, 4])
    n = nx.triangles(GX, nodes=[2, 0, 4])
    assert dict(f) == dict(n)
