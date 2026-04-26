"""Parity for inner-dict order on all_pairs_dijkstra/bellman_ford*.

Bead br-r37-c1-6rphu — continuation of br-r37-c1-3dxfn (outer keys)
and br-r37-c1-5ur50 (BFS inner). Five all_pairs_* dijkstra/bellman-
ford functions yielded inner per-source dicts in arbitrary Rust
internal order; nx returns them in (distance, BFS-tiebreak) order
from each source.
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
    "all_pairs_dijkstra_path",
    "all_pairs_dijkstra_path_length",
    "all_pairs_bellman_ford_path",
    "all_pairs_bellman_ford_path_length",
])
def test_inner_keys_match_networkx(name):
    g = _make_str_graph(fnx)
    gx = _make_str_graph(nx)
    f = dict(getattr(fnx, name)(g))
    n = dict(getattr(nx, name)(gx))
    for source in n:
        assert list(f[source].keys()) == list(n[source].keys()), (
            f"{name}[{source}]: fnx={list(f[source].keys())} "
            f"nx={list(n[source].keys())}"
        )


@needs_nx
def test_all_pairs_dijkstra_tuple_inner_keys_match():
    g = _make_str_graph(fnx)
    gx = _make_str_graph(nx)
    f = dict(fnx.all_pairs_dijkstra(g))
    n = dict(nx.all_pairs_dijkstra(gx))
    for source in n:
        fdist, fpaths = f[source]
        ndist, npaths = n[source]
        assert list(fdist.keys()) == list(ndist.keys())
        assert list(fpaths.keys()) == list(npaths.keys())


@needs_nx
def test_weighted_dijkstra_inner_uses_distance_order():
    """For weighted graphs the BFS order and distance order differ;
    nx uses distance order — fnx must too."""
    g = fnx.Graph()
    gx = nx.Graph()
    for u, v, w in [("c", "a", 10), ("c", "b", 1), ("b", "d", 1)]:
        g.add_edge(u, v, weight=w)
        gx.add_edge(u, v, weight=w)
    f = dict(fnx.all_pairs_dijkstra_path(g, weight="weight"))
    n = dict(nx.all_pairs_dijkstra_path(gx, weight="weight"))
    for source in n:
        assert list(f[source].keys()) == list(n[source].keys())


@needs_nx
def test_path_graph_inner_unchanged():
    """Regression: simple int graphs that already worked must continue."""
    g = fnx.path_graph(4)
    gx = nx.path_graph(4)
    f = dict(fnx.all_pairs_dijkstra_path(g))
    n = dict(nx.all_pairs_dijkstra_path(gx))
    for source in n:
        assert list(f[source].keys()) == list(n[source].keys())


@needs_nx
def test_inner_values_unchanged():
    g = _make_str_graph(fnx)
    gx = _make_str_graph(nx)
    f = dict(fnx.all_pairs_dijkstra_path_length(g))
    n = dict(nx.all_pairs_dijkstra_path_length(gx))
    for source in n:
        for target in n[source]:
            assert f[source][target] == n[source][target]


@needs_nx
def test_disconnected_components_inner_keys_match():
    g = fnx.Graph([("a", "b"), ("c", "d")])
    gx = nx.Graph([("a", "b"), ("c", "d")])
    f = dict(fnx.all_pairs_dijkstra_path(g))
    n = dict(nx.all_pairs_dijkstra_path(gx))
    for source in n:
        assert list(f[source].keys()) == list(n[source].keys())
