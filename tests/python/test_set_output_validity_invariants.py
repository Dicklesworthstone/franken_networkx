"""Oracle-free output-validity invariants for set-returning algorithms.

Verifying that a result actually satisfies its definition is the
metamorphic class that surfaced the node_connectivity P1s. Here:

* ``dominating_set`` dominates every node
* ``min_weighted_vertex_cover`` covers every edge
* ``maximal_independent_set`` is independent AND maximal
* every ``find_cliques`` result is a maximal clique
* ``greedy_color`` is a proper colouring

br-r37-c1-5gwjo
"""

from __future__ import annotations

import random

import pytest
import franken_networkx as fnx
from franken_networkx.algorithms import approximation as fnx_approx


def _graph(seed, p=0.35):
    rng = random.Random(seed)
    n = rng.randint(6, 12)
    g = fnx.Graph()
    g.add_nodes_from(range(n))
    for u in range(n):
        for v in range(u + 1, n):
            if rng.random() < p:
                g.add_edge(u, v)
    adj = {x: set(g.neighbors(x)) for x in g}
    return g, adj


@pytest.mark.parametrize("seed", range(60))
def test_dominating_set_dominates(seed):
    g, adj = _graph(seed)
    d = set(fnx.dominating_set(g))
    assert all(x in d or (adj[x] & d) for x in g)


@pytest.mark.parametrize("seed", range(60))
def test_vertex_cover_covers_every_edge(seed):
    g, _ = _graph(seed)
    cover = set(fnx_approx.min_weighted_vertex_cover(g))
    assert all(u in cover or v in cover for u, v in g.edges())


@pytest.mark.parametrize("seed", range(60))
def test_maximal_independent_set_is_independent_and_maximal(seed):
    g, adj = _graph(seed)
    iset = set(fnx.maximal_independent_set(g, seed=seed))
    # Independent: no two members adjacent.
    assert not any(v in adj[u] for u in iset for v in iset if u != v)
    # Maximal: every outside node is adjacent to a member.
    assert all((x in iset) or (adj[x] & iset) for x in g)


@pytest.mark.parametrize("seed", range(60))
def test_find_cliques_returns_maximal_cliques(seed):
    g, adj = _graph(seed)
    for clique in fnx.find_cliques(g):
        members = set(clique)
        # Actually a clique.
        assert all(b in adj[a] for a in members for b in members if a != b)
        # Maximal: no external node is adjacent to every member.
        assert not any(members <= adj[x] for x in g if x not in members)


@pytest.mark.parametrize("seed", range(60))
def test_greedy_color_is_proper(seed):
    g, _ = _graph(seed)
    coloring = fnx.greedy_color(g)
    assert all(coloring[u] != coloring[v] for u, v in g.edges())
