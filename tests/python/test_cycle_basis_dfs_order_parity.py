"""Parity for ``cycle_basis`` cycle-node-list ordering.

Bead br-r37-c1-j5swc. nx emits cycle node lists in DFS-discovery order
through the chord-completion path (e.g. ['b','a','c']) — i.e. the
order the back-edge walk visits nodes, not canonical node order.
The Rust binding returned cycles in canonical (node-sorted) order.

Drop-in code that iterates cycle nodes in nx's algorithmic order
(e.g. for parameterising a cycle visualisation, or for computing
edges from a cycle) broke.
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
def test_repro_two_chord_cycle_matches_nx():
    edges = [("c", "d"), ("a", "b"), ("b", "c"), ("d", "e"), ("a", "c")]
    g = _make_graph(fnx, edges)
    gx = _make_graph(nx, edges)
    assert fnx.cycle_basis(g) == nx.cycle_basis(gx)


@needs_nx
def test_triangle_matches_nx():
    edges = [("a", "b"), ("b", "c"), ("c", "a")]
    g = _make_graph(fnx, edges)
    gx = _make_graph(nx, edges)
    assert fnx.cycle_basis(g) == nx.cycle_basis(gx)


@needs_nx
def test_int_node_triangle_with_pendant_matches_nx():
    edges = [(0, 1), (1, 2), (2, 0), (2, 3)]
    g = _make_graph(fnx, edges)
    gx = _make_graph(nx, edges)
    assert fnx.cycle_basis(g) == nx.cycle_basis(gx)


@needs_nx
def test_root_argument_matches_nx():
    edges = [("a", "b"), ("b", "c"), ("c", "a"), ("c", "d")]
    g = _make_graph(fnx, edges)
    gx = _make_graph(nx, edges)
    assert fnx.cycle_basis(g, root="a") == nx.cycle_basis(gx, root="a")


@needs_nx
def test_two_separate_cycles_match_nx():
    edges = [
        ("a", "b"), ("b", "c"), ("c", "a"),
        ("d", "e"), ("e", "f"), ("f", "d"),
    ]
    g = _make_graph(fnx, edges)
    gx = _make_graph(nx, edges)
    assert fnx.cycle_basis(g) == nx.cycle_basis(gx)


@needs_nx
def test_tree_no_cycles_returns_empty():
    g = fnx.path_graph(5)
    gx = nx.path_graph(5)
    assert fnx.cycle_basis(g) == nx.cycle_basis(gx) == []


@needs_nx
def test_complete_graph_cycles_match_nx():
    g = fnx.complete_graph(4)
    gx = nx.complete_graph(4)
    assert fnx.cycle_basis(g) == nx.cycle_basis(gx)


@needs_nx
def test_grid_cycles_match_nx():
    g = fnx.grid_graph([3, 3])
    gx = nx.grid_graph([3, 3])
    assert fnx.cycle_basis(g) == nx.cycle_basis(gx)


@needs_nx
def test_multigraph_raises_not_implemented():
    """fnx mirrors nx's pre-computation error on MultiGraph."""
    mg = fnx.MultiGraph([(0, 1), (0, 1)])
    with pytest.raises(fnx.NetworkXNotImplemented, match="multigraph"):
        fnx.cycle_basis(mg)


@needs_nx
def test_empty_graph():
    g = fnx.Graph()
    gx = nx.Graph()
    assert fnx.cycle_basis(g) == nx.cycle_basis(gx) == []
