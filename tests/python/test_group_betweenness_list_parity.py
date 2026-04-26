"""Parity for ``group_betweenness_centrality`` list-of-groups handling.

Bead br-r37-c1-q49py. When ``C`` is a list of groups (e.g.,
``[[0, 1], [2, 3]]``), nx returns a list of per-group scores. fnx's
fast path (undirected, unweighted, no endpoints) always returned a
single scalar — the list-of-groups case was misrouted and produced
``0.0`` instead of the correct list of per-group values. Drop-in code
iterating the list of scores broke.

The slow path (weighted/directed/endpoints) already detected the
list-of-groups case correctly; only the Rust-fast-path branch needed
the same detection.
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


@needs_nx
def test_single_group_returns_scalar():
    G = fnx.path_graph(5)
    GX = nx.path_graph(5)
    f = fnx.group_betweenness_centrality(G, [0, 1])
    n = nx.group_betweenness_centrality(GX, [0, 1])
    assert isinstance(f, float)
    assert f == n


@needs_nx
def test_list_of_groups_returns_list():
    G = fnx.path_graph(5)
    GX = nx.path_graph(5)
    f = fnx.group_betweenness_centrality(G, [[0, 1], [2, 3]])
    n = nx.group_betweenness_centrality(GX, [[0, 1], [2, 3]])
    assert isinstance(f, list)
    assert isinstance(n, list)
    assert len(f) == len(n) == 2
    for fv, nv in zip(f, n):
        assert abs(fv - nv) < 1e-9


@needs_nx
def test_list_of_groups_non_normalized():
    G = fnx.path_graph(5)
    GX = nx.path_graph(5)
    f = fnx.group_betweenness_centrality(G, [[0, 1], [2, 3]], normalized=False)
    n = nx.group_betweenness_centrality(GX, [[0, 1], [2, 3]], normalized=False)
    assert isinstance(f, list)
    for fv, nv in zip(f, n):
        assert abs(fv - nv) < 1e-9


@needs_nx
def test_three_groups():
    G = fnx.complete_graph(8)
    GX = nx.complete_graph(8)
    f = fnx.group_betweenness_centrality(G, [[0, 1], [2, 3], [4, 5]])
    n = nx.group_betweenness_centrality(GX, [[0, 1], [2, 3], [4, 5]])
    assert isinstance(f, list)
    assert len(f) == 3
    for fv, nv in zip(f, n):
        assert abs(fv - nv) < 1e-9


@needs_nx
def test_empty_outer_list_on_null_graph_returns_empty_list():
    """C=[] on null graph returns empty list on both."""
    G = fnx.empty_graph(0)
    GX = nx.empty_graph(0)
    f = fnx.group_betweenness_centrality(G, [])
    n = nx.group_betweenness_centrality(GX, [])
    assert f == n == []


@needs_nx
def test_single_group_singleton_list_does_not_misroute():
    """A single-group call where the group happens to be a one-node list
    must still return a scalar, not a 1-element list."""
    G = fnx.path_graph(5)
    GX = nx.path_graph(5)
    f = fnx.group_betweenness_centrality(G, [2])
    n = nx.group_betweenness_centrality(GX, [2])
    assert isinstance(f, float)
    assert f == n
