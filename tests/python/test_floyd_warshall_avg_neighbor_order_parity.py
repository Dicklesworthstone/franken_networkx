"""Parity for floyd_warshall and average_neighbor_degree dict order.

Bead br-r37-c1-h1kf2. Three more dict-order drifts:

- ``floyd_warshall`` outer keys in arbitrary Rust order; nx uses
  node-insertion order. Inner per-source dicts driven by the
  algorithm's defaultdict access pattern (G.nodes() iteration in the
  triple loop) are also algorithm-specific.
- ``floyd_warshall_predecessor_and_distance`` tuple's predecessor
  dict has the same outer-key drift.
- ``average_neighbor_degree`` returns dict in sorted-key order; nx
  returns node-insertion order.

For floyd_warshall variants, delegate to nx so the inner-dict
algorithm-dependent order is preserved exactly. Values are correct
in both libraries.
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


# ---------------------------------------------------------------------------
# floyd_warshall
# ---------------------------------------------------------------------------

@needs_nx
def test_floyd_warshall_outer_keys_match_networkx():
    g = _make_str_graph(fnx)
    gx = _make_str_graph(nx)
    f = dict(fnx.floyd_warshall(g))
    n = dict(nx.floyd_warshall(gx))
    assert list(f.keys()) == list(n.keys())


@needs_nx
def test_floyd_warshall_inner_keys_match_networkx():
    g = _make_str_graph(fnx)
    gx = _make_str_graph(nx)
    f = dict(fnx.floyd_warshall(g))
    n = dict(nx.floyd_warshall(gx))
    for source in n:
        assert list(f[source].keys()) == list(n[source].keys()), (
            f"inner[{source}]: fnx={list(f[source].keys())} "
            f"nx={list(n[source].keys())}"
        )


@needs_nx
def test_floyd_warshall_pred_and_dist_outer_keys_match():
    g = _make_str_graph(fnx)
    gx = _make_str_graph(nx)
    fpred, fdist = fnx.floyd_warshall_predecessor_and_distance(g)
    npred, ndist = nx.floyd_warshall_predecessor_and_distance(gx)
    assert list(fdist.keys()) == list(ndist.keys())
    assert list(fpred.keys()) == list(npred.keys())


@needs_nx
def test_floyd_warshall_values_match_networkx():
    """Sanity: distance values match (regardless of order)."""
    g = _make_str_graph(fnx)
    gx = _make_str_graph(nx)
    f = dict(fnx.floyd_warshall(g))
    n = dict(nx.floyd_warshall(gx))
    for source in n:
        for target in n[source]:
            assert f[source][target] == n[source][target]


# ---------------------------------------------------------------------------
# average_neighbor_degree
# ---------------------------------------------------------------------------

@needs_nx
def test_average_neighbor_degree_keys_match_networkx():
    g = _make_str_graph(fnx)
    gx = _make_str_graph(nx)
    f = fnx.average_neighbor_degree(g)
    n = nx.average_neighbor_degree(gx)
    assert list(f.keys()) == list(n.keys())


@needs_nx
def test_average_neighbor_degree_path_graph_unchanged():
    """Regression: simple int graphs that already worked must continue."""
    g = fnx.path_graph(5)
    gx = nx.path_graph(5)
    f = fnx.average_neighbor_degree(g)
    n = nx.average_neighbor_degree(gx)
    assert list(f.keys()) == list(n.keys())


@needs_nx
def test_average_neighbor_degree_values_unchanged():
    g = _make_str_graph(fnx)
    gx = _make_str_graph(nx)
    f = fnx.average_neighbor_degree(g)
    n = nx.average_neighbor_degree(gx)
    for k in n:
        assert abs(f[k] - n[k]) < 1e-9
