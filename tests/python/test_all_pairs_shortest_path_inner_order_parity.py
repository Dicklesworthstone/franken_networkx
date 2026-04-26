"""Parity for ``all_pairs_shortest_path*`` inner-dict BFS order.

Bead br-r37-c1-5ur50. fnx.all_pairs_shortest_path and
fnx.shortest_path_length(no source/target) yielded outer dict keys in
correct (node-insertion) order, but each per-source INNER dict
iterated in arbitrary Rust internal order. nx returns inner dicts in
BFS-visit-from-source order at each source. Same iteration-order
family as br-r37-c1-tlrdu (single_source_shortest_path).
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
def test_all_pairs_shortest_path_inner_keys_match_networkx():
    g = _make_str_graph(fnx)
    gx = _make_str_graph(nx)
    f = dict(fnx.all_pairs_shortest_path(g))
    n = dict(nx.all_pairs_shortest_path(gx))
    assert list(f.keys()) == list(n.keys())
    for source in n:
        assert list(f[source].keys()) == list(n[source].keys()), (
            f"inner[{source}] mismatch: fnx={list(f[source].keys())} "
            f"nx={list(n[source].keys())}"
        )


@needs_nx
def test_all_pairs_shortest_path_length_inner_keys_match_networkx():
    g = _make_str_graph(fnx)
    gx = _make_str_graph(nx)
    f = dict(fnx.all_pairs_shortest_path_length(g))
    n = dict(nx.all_pairs_shortest_path_length(gx))
    for source in n:
        assert list(f[source].keys()) == list(n[source].keys())


@needs_nx
def test_shortest_path_length_no_args_inner_keys_match_networkx():
    g = _make_str_graph(fnx)
    gx = _make_str_graph(nx)
    f = dict(fnx.shortest_path_length(g))
    n = dict(nx.shortest_path_length(gx))
    for source in n:
        assert list(f[source].keys()) == list(n[source].keys())


@needs_nx
def test_path_graph_inner_keys_unchanged():
    """Regression: simple int graphs that already worked must continue."""
    g = fnx.path_graph(4)
    gx = nx.path_graph(4)
    f = dict(fnx.all_pairs_shortest_path(g))
    n = dict(nx.all_pairs_shortest_path(gx))
    for source in n:
        assert list(f[source].keys()) == list(n[source].keys())


@needs_nx
def test_inner_values_unchanged():
    """Reordering must not change values."""
    g = _make_str_graph(fnx)
    gx = _make_str_graph(nx)
    f = dict(fnx.all_pairs_shortest_path(g))
    n = dict(nx.all_pairs_shortest_path(gx))
    for source in n:
        for target in n[source]:
            assert f[source][target] == n[source][target]


@needs_nx
def test_with_cutoff_inner_keys_match():
    g = _make_str_graph(fnx)
    gx = _make_str_graph(nx)
    f = dict(fnx.all_pairs_shortest_path(g, cutoff=2))
    n = dict(nx.all_pairs_shortest_path(gx, cutoff=2))
    for source in n:
        assert list(f[source].keys()) == list(n[source].keys())


@needs_nx
def test_disconnected_components_inner_keys():
    g = fnx.Graph([("a", "b"), ("c", "d")])
    gx = nx.Graph([("a", "b"), ("c", "d")])
    f = dict(fnx.all_pairs_shortest_path(g))
    n = dict(nx.all_pairs_shortest_path(gx))
    for source in n:
        assert list(f[source].keys()) == list(n[source].keys())
