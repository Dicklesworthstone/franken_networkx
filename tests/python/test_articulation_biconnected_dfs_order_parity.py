"""Parity for ``articulation_points`` and ``biconnected_component_edges`` order.

Bead br-r37-c1-9kyjl. Two more iteration-order drifts:

- ``articulation_points`` returned APs in canonical/sorted order;
  nx yields them in DFS-discovery order from the algorithm.
- ``biconnected_component_edges`` yielded edge tuples in canonical
  (lower-id-first) form; nx yields them in DFS-traversal direction
  (e.g. ``('b', 'a')`` instead of ``('a', 'b')``).

Drop-in code that iterates these in algorithm-specific order broke.
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


def _make_str_graph(lib):
    g = lib.Graph()
    for u, v in [("c", "d"), ("a", "b"), ("b", "c"), ("d", "e")]:
        g.add_edge(u, v)
    return g


@needs_nx
def test_articulation_points_dfs_order_matches_networkx():
    g = _make_str_graph(fnx)
    gx = _make_str_graph(nx)
    f = list(fnx.articulation_points(g))
    n = list(nx.articulation_points(gx))
    assert f == n


@needs_nx
def test_biconnected_component_edges_direction_matches_networkx():
    g = _make_str_graph(fnx)
    gx = _make_str_graph(nx)
    f = list(fnx.biconnected_component_edges(g))
    n = list(nx.biconnected_component_edges(gx))
    assert f == n


@needs_nx
def test_articulation_points_path_graph_unchanged():
    g = fnx.path_graph(5)
    gx = nx.path_graph(5)
    f = list(fnx.articulation_points(g))
    n = list(nx.articulation_points(gx))
    assert f == n


@needs_nx
def test_articulation_points_no_aps():
    """Cycle has no articulation points."""
    g = fnx.cycle_graph(5)
    gx = nx.cycle_graph(5)
    f = list(fnx.articulation_points(g))
    n = list(nx.articulation_points(gx))
    assert f == n == []


@needs_nx
def test_articulation_points_complete_graph_no_aps():
    g = fnx.complete_graph(4)
    gx = nx.complete_graph(4)
    f = list(fnx.articulation_points(g))
    n = list(nx.articulation_points(gx))
    assert f == n == []


@needs_nx
def test_biconnected_component_edges_cycle_one_component():
    g = fnx.cycle_graph(4)
    gx = nx.cycle_graph(4)
    f = list(fnx.biconnected_component_edges(g))
    n = list(nx.biconnected_component_edges(gx))
    assert f == n


@needs_nx
def test_biconnected_component_edges_disconnected():
    """Each connected component has its own biconnected components."""
    g = fnx.Graph([("a", "b"), ("c", "d")])
    gx = nx.Graph([("a", "b"), ("c", "d")])
    f = list(fnx.biconnected_component_edges(g))
    n = list(nx.biconnected_component_edges(gx))
    assert f == n
