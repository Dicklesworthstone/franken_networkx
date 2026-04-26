"""Parity for ``single_source_dijkstra/bellman_ford*`` distance-order.

Bead br-r37-c1-62jy2. fnx yielded outer dict keys in arbitrary Rust
internal order; nx returns the dict with keys sorted by ascending
shortest-path distance from source (with adj-iteration order as
tiebreak — i.e. BFS-from-source visit order at each distance level).
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
@pytest.mark.parametrize("name", [
    "single_source_dijkstra_path",
    "single_source_dijkstra_path_length",
    "single_source_bellman_ford_path",
    "single_source_bellman_ford_path_length",
])
def test_single_source_unweighted_distance_order(name):
    g = _make_str_graph(fnx)
    gx = _make_str_graph(nx)
    f = list(getattr(fnx, name)(g, "c").keys())
    n = list(getattr(nx, name)(gx, "c").keys())
    assert f == n


@needs_nx
def test_single_source_dijkstra_tuple_dist_keys_match():
    g = _make_str_graph(fnx)
    gx = _make_str_graph(nx)
    fd, fp = fnx.single_source_dijkstra(g, "c")
    nd, np_ = nx.single_source_dijkstra(gx, "c")
    assert list(fd.keys()) == list(nd.keys())
    assert list(fp.keys()) == list(np_.keys())


@needs_nx
def test_single_source_bellman_ford_tuple_dist_keys_match():
    g = _make_str_graph(fnx)
    gx = _make_str_graph(nx)
    fd, fp = fnx.single_source_bellman_ford(g, "c")
    nd, np_ = nx.single_source_bellman_ford(gx, "c")
    assert list(fd.keys()) == list(nd.keys())


@needs_nx
def test_shortest_path_with_source_distance_order():
    g = _make_str_graph(fnx)
    gx = _make_str_graph(nx)
    f = list(fnx.shortest_path(g, source="c").keys())
    n = list(nx.shortest_path(gx, source="c").keys())
    assert f == n


@needs_nx
def test_weighted_dijkstra_uses_distance_order_not_bfs():
    """For weighted graphs the BFS order and distance order differ;
    nx uses distance order — fnx must too."""
    g = fnx.Graph()
    gx = nx.Graph()
    for u, v, w in [("c", "a", 10), ("c", "b", 1), ("b", "d", 1)]:
        g.add_edge(u, v, weight=w)
        gx.add_edge(u, v, weight=w)
    f = list(fnx.single_source_dijkstra_path(g, "c", weight="weight").keys())
    n = list(nx.single_source_dijkstra_path(gx, "c", weight="weight").keys())
    # By distance: c=0, b=1, d=2, a=10
    assert f == n == ["c", "b", "d", "a"]


@needs_nx
def test_unweighted_int_path_graph_unchanged():
    """Regression: simple int graphs that already worked must still."""
    g = fnx.path_graph(5)
    gx = nx.path_graph(5)
    f = list(fnx.single_source_dijkstra_path(g, 2).keys())
    n = list(nx.single_source_dijkstra_path(gx, 2).keys())
    assert f == n


@needs_nx
def test_values_unchanged():
    """Reordering must not change values."""
    g = _make_str_graph(fnx)
    gx = _make_str_graph(nx)
    f = fnx.single_source_dijkstra_path(g, "c")
    n = nx.single_source_dijkstra_path(gx, "c")
    for tgt in n:
        assert f[tgt] == n[tgt]
