"""Clustering-coefficient identities (clustering <-> triangles <-> transitivity).

The clustering functions are tied together by definition:
  - local clustering(v) = 2 * triangles(v) / (deg(v) * (deg(v) - 1)), deg >= 2;
  - transitivity = 3 * (number of triangles) / (number of length-2 paths);
  - average_clustering = mean of the local clustering values;
  - sum_v triangles(v) = 3 * (number of triangles);
  - every clustering value lies in [0, 1].
These cross-check clustering, triangles, transitivity, average_clustering, and
degree against each other, independent of networkx.

No mocks: real fnx.
"""

from __future__ import annotations

import random

import pytest
import franken_networkx as fnx


def _graph(seed):
    r = random.Random(seed)
    n = r.randint(5, 11)
    edges = [(u, v) for u in range(n) for v in range(u + 1, n) if r.random() < 0.4]
    g = fnx.Graph(); g.add_nodes_from(range(n)); g.add_edges_from(edges)
    return g, n


@pytest.mark.parametrize("seed", range(40))
def test_local_clustering_formula(seed):
    g, n = _graph(seed)
    tri = fnx.triangles(g)
    deg = dict(g.degree())
    clus = fnx.clustering(g)
    for v in g:
        if deg[v] >= 2:
            expected = 2 * tri[v] / (deg[v] * (deg[v] - 1))
            assert abs(clus[v] - expected) < 1e-9
        else:
            assert clus[v] == 0          # undefined degree<2 → 0 by convention
        assert 0 <= clus[v] <= 1 + 1e-9   # clustering is a fraction


@pytest.mark.parametrize("seed", range(40))
def test_transitivity_and_average_clustering(seed):
    g, n = _graph(seed)
    tri = fnx.triangles(g)
    deg = dict(g.degree())
    triangles_total = sum(tri.values()) // 3
    # sum of per-node triangle counts is 3x the number of triangles.
    assert sum(tri.values()) == 3 * triangles_total

    triads = sum(deg[v] * (deg[v] - 1) // 2 for v in g)  # length-2 paths
    if triads > 0:
        assert abs(fnx.transitivity(g) - 3 * triangles_total / triads) < 1e-9
    else:
        assert fnx.transitivity(g) == 0

    clus = fnx.clustering(g)
    assert abs(fnx.average_clustering(g) - sum(clus.values()) / n) < 1e-9


def test_complete_graph_clustering_is_one():
    # Every node in K_n (n>=3) has clustering 1 and transitivity 1.
    for n in (3, 4, 5):
        g = fnx.complete_graph(n)
        assert all(abs(c - 1.0) < 1e-9 for c in fnx.clustering(g).values())
        assert abs(fnx.transitivity(g) - 1.0) < 1e-9
