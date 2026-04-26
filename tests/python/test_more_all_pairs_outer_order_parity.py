"""Parity for outer-key order on more all_pairs_* path functions.

Bead br-r37-c1-sk5be — continuation of br-r37-c1-3dxfn. Three more
all_pairs_* functions yielded source keys in arbitrary Rust internal
order; nx iterates in node-insertion order:

- ``all_pairs_bellman_ford_path``
- ``all_pairs_bellman_ford_path_length``
- ``all_pairs_dijkstra``

Drop-in code that does ``for source, dists in result: ...`` got
different orders.
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
    "all_pairs_bellman_ford_path",
    "all_pairs_bellman_ford_path_length",
    "all_pairs_dijkstra",
])
def test_outer_keys_in_node_insertion_order(name):
    g = _make_str_graph(fnx)
    gx = _make_str_graph(nx)
    f = dict(getattr(fnx, name)(g))
    n = dict(getattr(nx, name)(gx))
    assert list(f.keys()) == list(n.keys()) == ["c", "d", "a", "b", "e"]


@needs_nx
@pytest.mark.parametrize("name", [
    "all_pairs_bellman_ford_path",
    "all_pairs_bellman_ford_path_length",
    "all_pairs_dijkstra",
])
def test_outer_keys_path_graph_unchanged(name):
    """Regression: simple int graphs must continue to work."""
    g = fnx.path_graph(4)
    gx = nx.path_graph(4)
    f = dict(getattr(fnx, name)(g))
    n = dict(getattr(nx, name)(gx))
    assert list(f.keys()) == list(n.keys()) == [0, 1, 2, 3]


@needs_nx
def test_all_pairs_dijkstra_with_weights_matches_networkx_outer():
    """Weighted path delegates to nx; outer keys still must match."""
    g = fnx.Graph()
    g.add_edge("a", "b", weight=2.5)
    g.add_edge("b", "c", weight=1.5)
    gx = nx.Graph()
    gx.add_edge("a", "b", weight=2.5)
    gx.add_edge("b", "c", weight=1.5)
    f = dict(fnx.all_pairs_dijkstra(g, weight="weight"))
    n = dict(nx.all_pairs_dijkstra(gx, weight="weight"))
    assert list(f.keys()) == list(n.keys())


@needs_nx
def test_all_pairs_bellman_ford_path_length_values_match():
    """Sanity: per-source distance values must match (regardless of
    inner-dict order)."""
    g = _make_str_graph(fnx)
    gx = _make_str_graph(nx)
    f = dict(fnx.all_pairs_bellman_ford_path_length(g))
    n = dict(nx.all_pairs_bellman_ford_path_length(gx))
    for source in n:
        for target in n[source]:
            assert f[source][target] == n[source][target]


@needs_nx
def test_all_pairs_dijkstra_with_cutoff_outer_keys():
    g = _make_str_graph(fnx)
    gx = _make_str_graph(nx)
    f = dict(fnx.all_pairs_dijkstra(g, cutoff=2))
    n = dict(nx.all_pairs_dijkstra(gx, cutoff=2))
    assert list(f.keys()) == list(n.keys())
