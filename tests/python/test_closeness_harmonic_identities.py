"""Closeness / harmonic centrality identities (centrality <-> distances).

On a connected graph these centralities are defined directly from the shortest-
path distances, so they cross-check all_pairs_shortest_path_length:
  - closeness(v) = (n - 1) / sum_u d(v, u);
  - harmonic(v) = sum_{u != v} 1 / d(v, u);
  - closeness(v) <= 1 (maximised when v is adjacent to every other node).
Oracle-free, independent of networkx.

No mocks: real fnx on connected graphs.
"""

from __future__ import annotations

import random

import pytest
import franken_networkx as fnx


def _connected(seed):
    r = random.Random(seed)
    n = r.randint(5, 10)
    edges = [(u, v) for u in range(n) for v in range(u + 1, n) if r.random() < 0.4]
    g = fnx.Graph(); g.add_nodes_from(range(n)); g.add_edges_from(edges)
    return g, n


@pytest.mark.parametrize("seed", range(40))
def test_closeness_and_harmonic_from_distances(seed):
    g, n = _connected(seed)
    if not fnx.is_connected(g) or g.number_of_edges() == 0:
        pytest.skip("disconnected / empty")
    apsp = dict(fnx.all_pairs_shortest_path_length(g))
    clo = fnx.closeness_centrality(g)
    har = fnx.harmonic_centrality(g)
    for v in g:
        distsum = sum(apsp[v][u] for u in g if u != v)
        assert distsum > 0
        assert abs(clo[v] - (n - 1) / distsum) < 1e-6
        expected_har = sum(1 / apsp[v][u] for u in g if u != v)
        assert abs(har[v] - expected_har) < 1e-6
        assert clo[v] <= 1 + 1e-9


def test_star_center_has_maximal_closeness():
    # In a star, the center is distance 1 from all leaves -> closeness 1;
    # a leaf is distance 1 to center and 2 to other leaves.
    g = fnx.star_graph(5)  # center 0, leaves 1..5
    clo = fnx.closeness_centrality(g)
    assert abs(clo[0] - 1.0) < 1e-9
    assert clo[0] == max(clo.values())
    # Harmonic of the center = number of leaves (all at distance 1).
    har = fnx.harmonic_centrality(g)
    assert abs(har[0] - 5) < 1e-9


def test_complete_graph_all_closeness_one():
    for n in (3, 4, 5):
        clo = fnx.closeness_centrality(fnx.complete_graph(n))
        assert all(abs(c - 1.0) < 1e-9 for c in clo.values())
