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

import itertools
import random

import pytest
import networkx as nx
import franken_networkx as fnx


def _count_triangles(g):
    """Triangle count by direct enumeration — an oracle independent of fnx.

    The identity `sum_v triangles(v) == 3 * T` needs a T that did not come from
    that same sum; deriving T as `sum // 3` reduces the check to divisibility.
    """
    return sum(
        1
        for a, b, c in itertools.combinations(sorted(g.nodes()), 3)
        if g.has_edge(a, b) and g.has_edge(b, c) and g.has_edge(a, c)
    )


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
    # Count triangles independently: deriving the total as sum//3 and comparing
    # would only assert that the sum is divisible by 3.
    triangles_total = _count_triangles(g)
    # sum of per-node triangle counts is 3x the number of triangles.
    assert sum(tri.values()) == 3 * triangles_total

    triads = sum(deg[v] * (deg[v] - 1) // 2 for v in g)  # length-2 paths
    if triads > 0:
        assert abs(fnx.transitivity(g) - 3 * triangles_total / triads) < 1e-9
    else:
        assert fnx.transitivity(g) == 0

    clus = fnx.clustering(g)
    assert abs(fnx.average_clustering(g) - sum(clus.values()) / n) < 1e-9


@pytest.mark.parametrize("seed", range(40))
def test_scalar_and_nbunch_forms_agree_with_the_dict(seed):
    """clustering(G, v) and triangles(G, v) return scalars by a separate path."""
    g, _ = _graph(seed)
    clus, tri = fnx.clustering(g), fnx.triangles(g)
    for v in g.nodes():
        assert fnx.clustering(g, v) == clus[v]
        assert fnx.triangles(g, v) == tri[v]
    subset = list(g.nodes())[:3]
    assert fnx.triangles(g, subset) == {v: tri[v] for v in subset}


@pytest.mark.parametrize("seed", range(40))
def test_average_clustering_count_zeros_contract(seed):
    """count_zeros=False changes the DENOMINATOR, and is undefined when all are 0."""
    g, _ = _graph(seed)
    nxg = nx.Graph(); nxg.add_nodes_from(g.nodes()); nxg.add_edges_from(g.edges())
    values = list(fnx.clustering(g).values())
    nonzero = [c for c in values if c != 0]

    if not nonzero:
        # Every clustering value is 0, so the divisor is 0. networkx raises here
        # and so must fnx — pinned rather than skipped, since it is a contract.
        with pytest.raises(ZeroDivisionError):
            fnx.average_clustering(g, count_zeros=False)
        with pytest.raises(ZeroDivisionError):
            nx.average_clustering(nxg, count_zeros=False)
    else:
        got = fnx.average_clustering(g, count_zeros=False)
        assert got == pytest.approx(sum(nonzero) / len(nonzero))
        assert got == pytest.approx(nx.average_clustering(nxg, count_zeros=False))


@pytest.mark.parametrize("n", [3, 4, 5, 6])
def test_complete_graph_triangle_count_is_n_choose_3(n):
    g = fnx.complete_graph(n)
    expected = n * (n - 1) * (n - 2) // 6
    assert _count_triangles(g) == expected
    assert sum(fnx.triangles(g).values()) == 3 * expected


def test_complete_graph_clustering_is_one():
    # Every node in K_n (n>=3) has clustering 1 and transitivity 1.
    for n in (3, 4, 5):
        g = fnx.complete_graph(n)
        assert all(abs(c - 1.0) < 1e-9 for c in fnx.clustering(g).values())
        assert abs(fnx.transitivity(g) - 1.0) < 1e-9
