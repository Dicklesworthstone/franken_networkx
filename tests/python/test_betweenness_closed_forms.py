"""Betweenness centrality closed forms + normalization relationship.

Betweenness has clean closed forms and structural bounds that are oracle-free:
  - complete graph K_n: every pair is adjacent, so no node is an intermediary
    and all betweenness values are 0;
  - star graph: the center lies on every leaf-leaf shortest path (normalized
    betweenness 1), every leaf has 0;
  - all values are >= 0, and normalized values are <= 1;
  - unnormalized = normalized * (n-1)(n-2)/2.
Independent of networkx.

That last relation is the UNDIRECTED one. On a digraph an ordered pair (s,t) and
its reverse are distinct, so the scale is (n-1)(n-2) with no halving — measured
below, the undirected scale matches 0 of 30 directed draws while the directed one
matches all 30. The `endpoints` parameter likewise changes the definition rather
than the scale: counting a node on the pairs it terminates adds exactly (n-1) to
its unnormalized score. Both are pinned here.

No mocks: real fnx.
"""

from __future__ import annotations

import random

import pytest
import franken_networkx as fnx


@pytest.mark.parametrize("n", [4, 5, 6])
def test_complete_graph_betweenness_is_zero(n):
    bc = fnx.betweenness_centrality(fnx.complete_graph(n))
    assert all(abs(v) < 1e-9 for v in bc.values())


@pytest.mark.parametrize("n", [4, 5, 6])
def test_star_betweenness(n):
    bc = fnx.betweenness_centrality(fnx.star_graph(n))  # center 0, leaves 1..n
    assert abs(bc[0] - 1.0) < 1e-9                       # center on every leaf pair
    assert all(abs(bc[i]) < 1e-9 for i in range(1, n + 1))  # leaves are 0


@pytest.mark.parametrize("seed", range(30))
def test_betweenness_bounds_and_normalization(seed):
    r = random.Random(seed)
    n = r.randint(5, 9)
    edges = [(u, v) for u in range(n) for v in range(u + 1, n) if r.random() < 0.4]
    g = fnx.Graph(); g.add_nodes_from(range(n)); g.add_edges_from(edges)

    bc = fnx.betweenness_centrality(g)
    assert all(v >= -1e-9 for v in bc.values())          # non-negative
    assert all(v <= 1 + 1e-9 for v in bc.values())       # normalized <= 1

    bcu = fnx.betweenness_centrality(g, normalized=False)
    scale = (n - 1) * (n - 2) / 2 if n > 2 else 1
    for v in g:
        assert abs(bcu[v] - bc[v] * scale) < 1e-6        # un/normalized relation


def _digraph(seed):
    r = random.Random(seed)
    n = r.randint(5, 9)
    d = fnx.DiGraph(); d.add_nodes_from(range(n))
    for u in range(n):
        for v in range(n):
            if u != v and r.random() < 0.3:
                d.add_edge(u, v)
    return d, n


@pytest.mark.parametrize("seed", range(30))
def test_directed_normalization_does_not_halve(seed):
    """Ordered pairs are distinct on a digraph, so the scale is (n-1)(n-2)."""
    d, n = _digraph(seed)
    bc = fnx.betweenness_centrality(d)
    bcu = fnx.betweenness_centrality(d, normalized=False)

    assert all(v >= -1e-9 for v in bc.values())
    assert all(v <= 1 + 1e-9 for v in bc.values())
    for v in d:
        assert abs(bcu[v] - bc[v] * (n - 1) * (n - 2)) < 1e-6
        # ...and NOT the undirected scale, which would be half of it.
        if bc[v] > 1e-9:
            assert abs(bcu[v] - bc[v] * (n - 1) * (n - 2) / 2) > 1e-9


def test_directed_family_has_nonzero_betweenness():
    """Guards the sweep: the scale relation is trivial where every value is 0."""
    nonzero = sum(
        1 for seed in range(30)
        if any(v > 1e-9 for v in fnx.betweenness_centrality(_digraph(seed)[0]).values())
    )
    assert nonzero >= 20, f"only {nonzero} of 30 digraphs have any betweenness"


@pytest.mark.parametrize("seed", range(30))
def test_endpoints_adds_exactly_n_minus_one(seed):
    """Counting a node on the pairs it terminates adds (n-1) unnormalized."""
    r = random.Random(seed)
    n = r.randint(5, 9)
    edges = [(u, v) for u in range(n) for v in range(u + 1, n) if r.random() < 0.4]
    g = fnx.Graph(); g.add_nodes_from(range(n)); g.add_edges_from(edges)

    without = fnx.betweenness_centrality(g, normalized=False)
    with_ends = fnx.betweenness_centrality(g, endpoints=True, normalized=False)
    # Monotone on every graph, connected or not.
    assert all(with_ends[v] >= without[v] - 1e-9 for v in g)

    if fnx.is_connected(g):
        # Every node terminates exactly n-1 pairs when all pairs are reachable.
        assert all(abs(with_ends[v] - (without[v] + (n - 1))) < 1e-6 for v in g)


def test_endpoints_lifts_path_endpoints_off_zero():
    """A path's endpoints intermediate nothing, so only `endpoints` can lift them."""
    g = fnx.path_graph(5)
    assert fnx.betweenness_centrality(g)[0] == 0
    assert fnx.betweenness_centrality(g, endpoints=True)[0] > 0


def test_path_middle_has_highest_betweenness():
    # On a path, the central node lies on the most shortest paths.
    g = fnx.path_graph(5)  # nodes 0..4, center 2
    bc = fnx.betweenness_centrality(g)
    assert bc[2] == max(bc.values())
    assert bc[0] == 0 and bc[4] == 0                     # endpoints intermediate nothing
