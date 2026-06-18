"""Betweenness centrality closed forms + normalization relationship.

Betweenness has clean closed forms and structural bounds that are oracle-free:
  - complete graph K_n: every pair is adjacent, so no node is an intermediary
    and all betweenness values are 0;
  - star graph: the center lies on every leaf-leaf shortest path (normalized
    betweenness 1), every leaf has 0;
  - all values are >= 0, and normalized values are <= 1;
  - unnormalized = normalized * (n-1)(n-2)/2.
Independent of networkx.

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


def test_path_middle_has_highest_betweenness():
    # On a path, the central node lies on the most shortest paths.
    g = fnx.path_graph(5)  # nodes 0..4, center 2
    bc = fnx.betweenness_centrality(g)
    assert bc[2] == max(bc.values())
    assert bc[0] == 0 and bc[4] == 0                     # endpoints intermediate nothing
