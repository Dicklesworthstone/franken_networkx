"""Parity for ``find_cycle`` undirected edge-tuple direction.

Bead br-r37-c1-2hrfs. On an undirected graph the Rust binding emitted
edge tuples in algorithm-canonical orientation, but nx emits them in
DFS-traversal direction (which depends on adj-iteration order).

Repro: edges = [(c,d),(a,b),(b,c),(d,e),(a,c)]
  fnx -> [('c','a'),('a','b'),('b','c')]   (edge tuples reversed)
  nx  -> [('c','b'),('b','a'),('a','c')]

Drop-in code that compared edge orientations from find_cycle to a
reference layout broke. Fix delegates undirected ``find_cycle`` to nx.
The directed case already matches without delegation.
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


def _make_digraph(lib, edges):
    g = lib.DiGraph()
    for u, v in edges:
        g.add_edge(u, v)
    return g


@needs_nx
def test_undirected_chord_cycle_direction_matches_nx():
    """Repro from the bead description."""
    edges = [("c", "d"), ("a", "b"), ("b", "c"), ("d", "e"), ("a", "c")]
    g = _make_graph(fnx, edges)
    gx = _make_graph(nx, edges)
    assert list(fnx.find_cycle(g)) == list(nx.find_cycle(gx))


@needs_nx
def test_undirected_triangle_matches_nx():
    edges = [("a", "b"), ("b", "c"), ("c", "a")]
    g = _make_graph(fnx, edges)
    gx = _make_graph(nx, edges)
    assert list(fnx.find_cycle(g)) == list(nx.find_cycle(gx))


@needs_nx
def test_undirected_int_node_triangle_with_pendant_matches_nx():
    edges = [(0, 1), (1, 2), (2, 0), (2, 3)]
    g = _make_graph(fnx, edges)
    gx = _make_graph(nx, edges)
    assert list(fnx.find_cycle(g)) == list(nx.find_cycle(gx))


@needs_nx
def test_undirected_with_source_kwarg_matches_nx():
    edges = [("a", "b"), ("b", "c"), ("c", "a"), ("d", "e"), ("e", "f"), ("f", "d")]
    g = _make_graph(fnx, edges)
    gx = _make_graph(nx, edges)
    assert list(fnx.find_cycle(g, source="d")) == list(nx.find_cycle(gx, source="d"))


@needs_nx
def test_undirected_no_cycle_raises_networkx_no_cycle():
    """Tree has no cycles: both libs raise NetworkXNoCycle."""
    g = fnx.path_graph(5)
    with pytest.raises(fnx.NetworkXNoCycle):
        list(fnx.find_cycle(g))


@needs_nx
def test_directed_still_matches_nx():
    """Sanity: the directed code path already matched and still does."""
    edges = [("c", "d"), ("a", "b"), ("b", "c"), ("d", "a"), ("c", "a")]
    dg = _make_digraph(fnx, edges)
    dgx = _make_digraph(nx, edges)
    assert list(fnx.find_cycle(dg)) == list(nx.find_cycle(dgx))


@needs_nx
def test_undirected_disconnected_with_cycle_in_one_component():
    """Cycle isolated from a tree component."""
    g = fnx.Graph()
    gx = nx.Graph()
    for u, v in [("a", "b"), ("b", "c"), ("c", "a"), ("x", "y"), ("y", "z")]:
        g.add_edge(u, v)
        gx.add_edge(u, v)
    assert list(fnx.find_cycle(g)) == list(nx.find_cycle(gx))


@needs_nx
def test_undirected_two_cycles_first_wins_matches_nx():
    """When multiple cycles exist, find_cycle returns the first
    discovered — nx and fnx must agree on which one."""
    g = fnx.Graph()
    gx = nx.Graph()
    for u, v in [(0, 1), (1, 2), (2, 0), (3, 4), (4, 5), (5, 3), (0, 3)]:
        g.add_edge(u, v)
        gx.add_edge(u, v)
    assert list(fnx.find_cycle(g)) == list(nx.find_cycle(gx))
