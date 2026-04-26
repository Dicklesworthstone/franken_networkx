"""Parity for ``communicability_betweenness_centrality`` dict iteration order.

Bead br-r37-c1-pm78h. fnx returned a dict in the Rust binding's
internal order (e.g. for ``path_graph(4)``: ``[1, 2, 0, 3]``) instead
of nx's node-insertion order (``[0, 1, 2, 3]``). Drop-in code that
iterates the result expecting node order — a common pattern: ``for
n, score in centrality.items(): ...`` — broke.

Values are unchanged; only iteration order differs.
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
def test_iteration_order_matches_node_insertion_order():
    G = fnx.path_graph(4)
    GX = nx.path_graph(4)
    f = fnx.communicability_betweenness_centrality(G)
    n = nx.communicability_betweenness_centrality(GX)
    assert list(f.keys()) == list(n.keys()) == [0, 1, 2, 3]


@needs_nx
def test_string_node_iteration_order():
    G = fnx.Graph()
    GX = nx.Graph()
    for u, v in [("a", "b"), ("b", "c"), ("c", "d")]:
        G.add_edge(u, v)
        GX.add_edge(u, v)
    f = fnx.communicability_betweenness_centrality(G)
    n = nx.communicability_betweenness_centrality(GX)
    assert list(f.keys()) == list(n.keys()) == ["a", "b", "c", "d"]


@needs_nx
def test_cycle_graph_iteration_order():
    G = fnx.cycle_graph(5)
    GX = nx.cycle_graph(5)
    f = fnx.communicability_betweenness_centrality(G)
    n = nx.communicability_betweenness_centrality(GX)
    assert list(f.keys()) == list(n.keys())


@needs_nx
def test_values_match_networkx_within_floating_point_noise():
    """Rust and nx may differ at the ~1e-14 level due to different
    matrix solvers. Values should still match within tolerance."""
    G = fnx.path_graph(5)
    GX = nx.path_graph(5)
    f = fnx.communicability_betweenness_centrality(G)
    n = nx.communicability_betweenness_centrality(GX)
    for k in n:
        assert abs(f[k] - n[k]) < 1e-9


@needs_nx
def test_post_add_node_order_preserved():
    """When new nodes are added after construction, iteration order
    follows insertion."""
    G = fnx.Graph()
    GX = nx.Graph()
    G.add_edges_from([(2, 3), (1, 2), (0, 1)])
    GX.add_edges_from([(2, 3), (1, 2), (0, 1)])
    f = fnx.communicability_betweenness_centrality(G)
    n = nx.communicability_betweenness_centrality(GX)
    assert list(f.keys()) == list(n.keys())


@needs_nx
def test_complete_graph_keys_set_match():
    """All node keys present (none dropped)."""
    G = fnx.complete_graph(4)
    GX = nx.complete_graph(4)
    f = fnx.communicability_betweenness_centrality(G)
    n = nx.communicability_betweenness_centrality(GX)
    assert set(f.keys()) == set(n.keys()) == {0, 1, 2, 3}
