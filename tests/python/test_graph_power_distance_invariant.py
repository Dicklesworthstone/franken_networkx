"""Graph power G^k distance invariant (power <-> shortest paths).

The k-th power of a graph has an edge (u, v) exactly when u and v are within
distance k in the original graph. This is the DEFINING property, cross-checking
power against all_pairs_shortest_path_length (the existing power test covers
nx parity, not this invariant):
  - G^k has edge (u, v) iff 1 <= dist(u, v) <= k;
  - G^1 == G;
  - for a connected graph, G^diameter is the complete graph.
Oracle-free, independent of networkx.

No mocks: real fnx.
"""

from __future__ import annotations

import random

import pytest
import franken_networkx as fnx


def _graph(seed):
    r = random.Random(seed)
    n = r.randint(5, 10)
    edges = [(u, v) for u in range(n) for v in range(u + 1, n) if r.random() < 0.35]
    g = fnx.Graph(); g.add_nodes_from(range(n)); g.add_edges_from(edges)
    return g, n


def _edge_set(g):
    return {tuple(sorted((u, v))) for u, v in g.edges()}


@pytest.mark.parametrize("seed", range(40))
@pytest.mark.parametrize("k", [1, 2, 3])
def test_power_edge_iff_within_distance_k(seed, k):
    g, n = _graph(seed)
    if g.number_of_edges() == 0:
        pytest.skip("no edges")
    apsp = dict(fnx.all_pairs_shortest_path_length(g))
    gk_edges = _edge_set(fnx.power(g, k))
    expected = {
        (u, v)
        for u in g for v in apsp[u]
        if u < v and 1 <= apsp[u][v] <= k
    }
    assert gk_edges == expected


@pytest.mark.parametrize("seed", range(40))
def test_power_one_is_identity(seed):
    g, n = _graph(seed)
    if g.number_of_edges() == 0:
        pytest.skip("no edges")
    assert _edge_set(fnx.power(g, 1)) == _edge_set(g)


@pytest.mark.parametrize("seed", range(40))
def test_power_diameter_is_complete(seed):
    g, n = _graph(seed)
    if not fnx.is_connected(g) or n < 2:
        pytest.skip("disconnected / trivial")
    d = fnx.diameter(g)
    gd = fnx.power(g, d)
    # Every pair is within the diameter, so G^diameter is complete.
    assert gd.number_of_edges() == n * (n - 1) // 2
