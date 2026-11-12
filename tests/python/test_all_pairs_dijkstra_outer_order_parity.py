"""Parity for ``all_pairs_dijkstra_path`` / ``_length`` outer-key order.

Bead br-r37-c1-3dxfn. fnx yielded source keys in arbitrary Rust
internal order; nx iterates in node-insertion order. Drop-in code
that does ``for source, dists in result: ...`` got different orders.

Note: this fix only addresses outer-key (source) order. Inner-dict
(per-source target order) follows the algorithm's BFS/Dijkstra
traversal and is implementation-specific in nx — not pinned here.
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
def test_all_pairs_dijkstra_path_outer_keys_node_order():
    g = _make_str_graph(fnx)
    gx = _make_str_graph(nx)
    f = dict(fnx.all_pairs_dijkstra_path(g))
    n = dict(nx.all_pairs_dijkstra_path(gx))
    assert list(f.keys()) == list(n.keys()) == ["c", "d", "a", "b", "e"]


@needs_nx
def test_all_pairs_dijkstra_path_length_outer_keys_node_order():
    g = _make_str_graph(fnx)
    gx = _make_str_graph(nx)
    f = dict(fnx.all_pairs_dijkstra_path_length(g))
    n = dict(nx.all_pairs_dijkstra_path_length(gx))
    assert list(f.keys()) == list(n.keys()) == ["c", "d", "a", "b", "e"]


@needs_nx
def test_path_graph_outer_keys_unchanged():
    """Regression: simple int graphs that already match must continue to."""
    g = fnx.path_graph(4)
    gx = nx.path_graph(4)
    f = dict(fnx.all_pairs_dijkstra_path(g))
    n = dict(nx.all_pairs_dijkstra_path(gx))
    assert list(f.keys()) == list(n.keys()) == [0, 1, 2, 3]


@needs_nx
def test_weighted_path_outer_keys_match_networkx():
    """Weighted path delegates to nx; outer keys still must match."""
    g = fnx.Graph()
    g.add_edge("a", "b", weight=2.5)
    g.add_edge("b", "c", weight=1.5)
    gx = nx.Graph()
    gx.add_edge("a", "b", weight=2.5)
    gx.add_edge("b", "c", weight=1.5)
    f = dict(fnx.all_pairs_dijkstra_path(g, weight="weight"))
    n = dict(nx.all_pairs_dijkstra_path(gx, weight="weight"))
    assert list(f.keys()) == list(n.keys())


@needs_nx
def test_with_cutoff_outer_keys_match():
    """cutoff path uses single_source_dijkstra under-the-hood; the
    outer iteration order is from G.nodes() directly so always matches."""
    g = _make_str_graph(fnx)
    gx = _make_str_graph(nx)
    f = dict(fnx.all_pairs_dijkstra_path(g, cutoff=2))
    n = dict(nx.all_pairs_dijkstra_path(gx, cutoff=2))
    assert list(f.keys()) == list(n.keys())


@needs_nx
def test_dijkstra_path_values_unchanged():
    g = _make_str_graph(fnx)
    gx = _make_str_graph(nx)
    f = dict(fnx.all_pairs_dijkstra_path(g))
    n = dict(nx.all_pairs_dijkstra_path(gx))
    # Per-source distances should match (regardless of inner-dict order).
    for source in n:
        for target in n[source]:
            assert f[source][target] == n[source][target]
