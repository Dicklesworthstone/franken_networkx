"""Parity for ``intersection`` node + edge iteration ordering.

Bead br-r37-c1-saf8a. nx implements intersection via Python set
intersection and ``add_nodes_from(set) / add_edges_from(set)``,
giving a hash-based (but stable + deterministic within a process)
node and edge iteration order. The Rust binding traversed internal
adjacency in a different order, drifting both the node order and
the edge tuple direction.

Drop-in code that iterated ``R.nodes()`` or ``R.edges()`` of an
intersection result silently broke. Sister ``difference`` /
``symmetric_difference`` ops were already matching nx and remain
on the Rust path.

Note: Python's set iteration order is process-dependent (hash
randomisation), so these tests can't pin a specific order — they
assert exact equality between fnx and nx on the same process.
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


def _build_pair(g_cls_pair, h_cls_pair, edges_g, edges_h):
    """Build an (fnx, nx) pair of graphs with synced node sets."""
    fg = g_cls_pair[0]()
    ng = g_cls_pair[1]()
    fh = h_cls_pair[0]()
    nh = h_cls_pair[1]()
    for u, v in edges_g:
        fg.add_edge(u, v)
        ng.add_edge(u, v)
    for u, v in edges_h:
        fh.add_edge(u, v)
        nh.add_edge(u, v)
    return fg, fh, ng, nh


@needs_nx
def test_str_node_intersection_node_and_edge_order_match_nx():
    fg, fh, ng, nh = _build_pair(
        (fnx.Graph, nx.Graph),
        (fnx.Graph, nx.Graph),
        [("a", "b"), ("b", "c"), ("c", "d")],
        [("a", "b"), ("c", "d"), ("d", "e")],
    )
    # Sync node sets (intersection requires same node set in nx default)
    for n in list(fh.nodes()):
        if n not in fg:
            fg.add_node(n)
            ng.add_node(n)
    for n in list(fg.nodes()):
        if n not in fh:
            fh.add_node(n)
            nh.add_node(n)
    f = fnx.intersection(fg, fh)
    n = nx.intersection(ng, nh)
    assert list(f.nodes()) == list(n.nodes())
    assert list(f.edges()) == list(n.edges())


@needs_nx
def test_int_node_intersection_matches_nx():
    fg, fh, ng, nh = _build_pair(
        (fnx.Graph, nx.Graph),
        (fnx.Graph, nx.Graph),
        [(0, 1), (1, 2), (2, 3)],
        [(0, 1), (2, 3), (3, 4)],
    )
    for n in list(fh.nodes()):
        if n not in fg:
            fg.add_node(n)
            ng.add_node(n)
    for n in list(fg.nodes()):
        if n not in fh:
            fh.add_node(n)
            nh.add_node(n)
    f = fnx.intersection(fg, fh)
    n = nx.intersection(ng, nh)
    assert list(f.nodes()) == list(n.nodes())
    assert list(f.edges()) == list(n.edges())


@needs_nx
def test_intersection_returns_correct_class_for_graph():
    fg = fnx.Graph([(0, 1)])
    fh = fnx.Graph([(0, 1)])
    f = fnx.intersection(fg, fh)
    assert type(f).__name__ == "Graph"
    assert isinstance(f, fnx.Graph)


@needs_nx
def test_intersection_returns_correct_class_for_digraph():
    fg, fh, ng, nh = _build_pair(
        (fnx.DiGraph, nx.DiGraph),
        (fnx.DiGraph, nx.DiGraph),
        [("a", "b"), ("b", "c"), ("c", "a")],
        [("a", "b"), ("c", "a"), ("a", "c")],
    )
    f = fnx.intersection(fg, fh)
    n = nx.intersection(ng, nh)
    assert type(f).__name__ == "DiGraph"
    assert isinstance(f, fnx.DiGraph)
    assert list(f.nodes()) == list(n.nodes())
    assert list(f.edges()) == list(n.edges())


@needs_nx
def test_intersection_returns_correct_class_for_multigraph():
    fg = fnx.MultiGraph([("a", "b")])
    fh = fnx.MultiGraph([("a", "b")])
    f = fnx.intersection(fg, fh)
    assert type(f).__name__ == "MultiGraph"
    assert isinstance(f, fnx.MultiGraph)


@needs_nx
def test_intersection_returns_correct_class_for_multidigraph():
    fg = fnx.MultiDiGraph([("a", "b")])
    fh = fnx.MultiDiGraph([("a", "b")])
    f = fnx.intersection(fg, fh)
    assert type(f).__name__ == "MultiDiGraph"
    assert isinstance(f, fnx.MultiDiGraph)


@needs_nx
def test_intersection_empty_edge_overlap():
    fg = fnx.Graph()
    fh = fnx.Graph()
    ng = nx.Graph()
    nh = nx.Graph()
    fg.add_edge(0, 1)
    ng.add_edge(0, 1)
    fh.add_edge(2, 3)
    nh.add_edge(2, 3)
    fg.add_nodes_from([2, 3])
    ng.add_nodes_from([2, 3])
    fh.add_nodes_from([0, 1])
    nh.add_nodes_from([0, 1])
    f = fnx.intersection(fg, fh)
    n = nx.intersection(ng, nh)
    assert list(f.edges()) == list(n.edges()) == []


@needs_nx
def test_intersection_identical_graphs():
    fg = fnx.Graph([(0, 1), (1, 2), (2, 0)])
    fh = fnx.Graph([(0, 1), (1, 2), (2, 0)])
    ng = nx.Graph([(0, 1), (1, 2), (2, 0)])
    nh = nx.Graph([(0, 1), (1, 2), (2, 0)])
    f = fnx.intersection(fg, fh)
    n = nx.intersection(ng, nh)
    assert list(f.nodes()) == list(n.nodes())
    assert list(f.edges()) == list(n.edges())


@needs_nx
def test_intersection_returns_fnx_graph_not_nx_graph():
    """Regression: must return fnx.Graph (drop-in contract)."""
    fg = fnx.Graph([(0, 1)])
    fh = fnx.Graph([(0, 1)])
    f = fnx.intersection(fg, fh)
    assert isinstance(f, fnx.Graph)


@needs_nx
def test_intersection_disjoint_node_sets_still_work():
    """nx allows disjoint node sets — result is empty graph."""
    fg = fnx.Graph([(0, 1), (1, 2)])
    fh = fnx.Graph([(0, 1)])
    ng = nx.Graph([(0, 1), (1, 2)])
    nh = nx.Graph([(0, 1)])
    f = fnx.intersection(fg, fh)
    n = nx.intersection(ng, nh)
    assert list(f.nodes()) == list(n.nodes())
    assert list(f.edges()) == list(n.edges())
