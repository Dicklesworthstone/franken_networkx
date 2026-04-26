"""Parity for ``min_weight_matching`` tuple direction.

Bead br-r37-c1-fs3bl. Same family pattern as br-r37-c1-kpnc8 which
fixed max_weight_matching. The Rust binding returned matched pairs
with different tuple directions than nx — the matching choice
itself was correct (same nodes paired), but per-pair tuples flipped.

Repro:
  edges = [(0,1),(0,2),(1,2),(2,3)]
  fnx -> {(0,1), (2,3)}
  nx  -> {(1,0), (3,2)}
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


def _make_graph(lib, edges, weighted=False, weight_attr="weight"):
    g = lib.Graph()
    for ed in edges:
        if weighted:
            u, v, w = ed
            g.add_edge(u, v, **{weight_attr: w})
        else:
            g.add_edge(*ed)
    return g


@needs_nx
def test_disjoint_edges_tuple_direction_matches_nx():
    edges = [(0, 1), (0, 2), (1, 2), (2, 3)]
    g = _make_graph(fnx, edges)
    gx = _make_graph(nx, edges)
    assert fnx.min_weight_matching(g) == nx.min_weight_matching(gx)


@needs_nx
def test_str_node_repro_matches_nx():
    edges = [("c", "d"), ("a", "b"), ("b", "c"), ("d", "e"), ("a", "c")]
    g = _make_graph(fnx, edges)
    gx = _make_graph(nx, edges)
    assert fnx.min_weight_matching(g) == nx.min_weight_matching(gx)


@needs_nx
def test_simple_two_disjoint_edges_matches_nx():
    edges = [("a", "b"), ("c", "d")]
    g = _make_graph(fnx, edges)
    gx = _make_graph(nx, edges)
    assert fnx.min_weight_matching(g) == nx.min_weight_matching(gx)


@needs_nx
def test_weighted_matching_matches_nx():
    edges = [("a", "b", 2), ("b", "c", 3), ("c", "a", 1), ("c", "d", 1)]
    g = _make_graph(fnx, edges, weighted=True)
    gx = _make_graph(nx, edges, weighted=True)
    assert fnx.min_weight_matching(g) == nx.min_weight_matching(gx)


@needs_nx
def test_custom_weight_attr_matches_nx():
    edges = [("a", "b", 2), ("b", "c", 3), ("c", "a", 1), ("c", "d", 1)]
    g = _make_graph(fnx, edges, weighted=True, weight_attr="custom_w")
    gx = _make_graph(nx, edges, weighted=True, weight_attr="custom_w")
    assert fnx.min_weight_matching(g, weight="custom_w") == nx.min_weight_matching(
        gx, weight="custom_w"
    )


@needs_nx
def test_complete_graph_k4_matches_nx():
    g = fnx.complete_graph(4)
    gx = nx.complete_graph(4)
    assert fnx.min_weight_matching(g) == nx.min_weight_matching(gx)


@needs_nx
def test_empty_graph_matches_nx():
    g = fnx.Graph()
    gx = nx.Graph()
    assert fnx.min_weight_matching(g) == nx.min_weight_matching(gx) == set()


@needs_nx
def test_single_edge_matches_nx():
    g = fnx.Graph([(0, 1)])
    gx = nx.Graph([(0, 1)])
    assert fnx.min_weight_matching(g) == nx.min_weight_matching(gx)


@needs_nx
def test_multigraph_projects_to_min_weight_per_parallel_edge():
    """MultiGraph input projects to simple Graph using the min weight
    per pair of parallel edges before delegation."""
    mg = fnx.MultiGraph()
    mg.add_edge(0, 1, weight=5)
    mg.add_edge(0, 1, weight=2)  # parallel — min=2 wins
    mg.add_edge(2, 3, weight=1)
    result = fnx.min_weight_matching(mg)
    # Both edges should be in the matching (independent edges).
    normalised = set(frozenset(e) for e in result)
    assert frozenset({0, 1}) in normalised
    assert frozenset({2, 3}) in normalised


@needs_nx
def test_min_edge_cover_unchanged_after_delegation():
    """min_edge_cover internally uses min_weight_matching via the
    odd-complete construction; verify it still works after the
    wrapper change (regression check)."""
    edges = [("a", "x"), ("a", "y"), ("b", "x"), ("b", "z"), ("c", "y"), ("c", "z")]
    g = _make_graph(fnx, edges)
    gx = _make_graph(nx, edges)
    f = fnx.min_edge_cover(g)
    n = nx.min_edge_cover(gx)
    # Both produce a valid edge cover; normalise to frozenset edges.
    assert set(frozenset(e) for e in f) == set(frozenset(e) for e in n)


@needs_nx
def test_bipartite_complete_k33_matches_nx():
    g = fnx.complete_bipartite_graph(3, 3)
    gx = nx.complete_bipartite_graph(3, 3)
    assert fnx.min_weight_matching(g) == nx.min_weight_matching(gx)
