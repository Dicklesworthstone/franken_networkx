"""Isomorphism invariants: relabeling, necessary-condition chain, parity.

Combines differential parity vs networkx with metamorphic relations:

* a graph is isomorphic to any relabeling of itself
* isomorphic graphs share invariants (degree sequence, triangle count)
* necessary-condition chain: ``is_isomorphic`` ==> ``could_be_isomorphic``
  ==> ``fast_could_be_isomorphic`` ==> ``faster_could_be_isomorphic``
* graphs with different edge counts are not isomorphic

br-r37-c1-b3dlu
"""

from __future__ import annotations

import random

import pytest
import networkx as nx
import franken_networkx as fnx


def _random_graph(seed, directed=False, p=0.4):
    rng = random.Random(seed)
    n = rng.randint(4, 8)
    g = (fnx.DiGraph if directed else fnx.Graph)()
    g.add_nodes_from(range(n))
    for u in range(n):
        for v in range(n):
            if u == v:
                continue
            if (directed or u < v) and rng.random() < p:
                g.add_edge(u, v)
    return g, n


@pytest.mark.parametrize("directed", [False, True])
@pytest.mark.parametrize("seed", range(50))
def test_graph_is_isomorphic_to_its_relabeling(directed, seed):
    g, n = _random_graph(seed, directed=directed)
    perm = list(range(n))
    random.Random(seed + 1).shuffle(perm)
    h = fnx.relabel_nodes(g, {i: perm[i] for i in range(n)})
    assert fnx.is_isomorphic(g, h)
    # Isomorphic graphs share degree sequence (and triangle count, undirected).
    assert sorted(d for _, d in g.degree()) == sorted(d for _, d in h.degree())
    if not directed:
        assert sum(fnx.triangles(g).values()) == sum(fnx.triangles(h).values())


@pytest.mark.parametrize("seed", range(80))
def test_necessary_condition_implication_chain(seed):
    g, n = _random_graph(seed)
    h, _ = _random_graph(seed * 7 + 1)
    # Align node counts so the comparison is meaningful.
    h.add_nodes_from(range(n))
    if fnx.is_isomorphic(g, h):
        assert fnx.could_be_isomorphic(g, h)
    if fnx.could_be_isomorphic(g, h):
        assert fnx.fast_could_be_isomorphic(g, h)
    if fnx.fast_could_be_isomorphic(g, h):
        assert fnx.faster_could_be_isomorphic(g, h)


@pytest.mark.parametrize("seed", range(60))
def test_is_isomorphic_matches_networkx(seed):
    g, _ = _random_graph(seed)
    h, _ = _random_graph(seed * 3 + 5)
    ng = nx.Graph(list(g.edges()))
    nh = nx.Graph(list(h.edges()))
    assert fnx.is_isomorphic(g, h) == nx.is_isomorphic(ng, nh)


def test_different_edge_count_not_isomorphic():
    g = fnx.Graph([(0, 1), (1, 2), (2, 0)])  # triangle
    h = fnx.Graph([(0, 1), (1, 2)])          # path
    assert not fnx.is_isomorphic(g, h)
    # The faster necessary condition also rejects it (degree sequences differ).
    assert not fnx.faster_could_be_isomorphic(g, h)
