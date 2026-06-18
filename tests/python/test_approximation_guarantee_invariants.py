"""Oracle-free output-validity + approximation-ratio guarantees.

Approximation algorithms carry provable guarantees that catch logic bugs
without any oracle:

* ``min_weighted_vertex_cover`` is a valid cover and (2-approx) is at most
  twice a maximum matching (a lower bound on the optimum)
* ``max_clique`` returns an actual clique; ``large_clique_size`` never
  exceeds the true maximum clique size
* ``steiner_tree`` spans every terminal and is a tree
* ``traveling_salesman_problem`` returns a closed cycle visiting all nodes

br-r37-c1-ttgwy
"""

from __future__ import annotations

import random

import pytest
import networkx as nx
import franken_networkx as fnx
from franken_networkx.algorithms import approximation as fnx_approx


def _graph(seed, p=0.4):
    rng = random.Random(seed)
    n = rng.randint(6, 11)
    g = fnx.Graph()
    g.add_nodes_from(range(n))
    for u in range(n):
        for v in range(u + 1, n):
            if rng.random() < p:
                g.add_edge(u, v)
    ng = nx.Graph(g.edges())
    ng.add_nodes_from(range(n))
    return g, ng, n


@pytest.mark.parametrize("seed", range(40))
def test_vertex_cover_valid_and_within_2x(seed):
    g, ng, _ = _graph(seed)
    cover = set(fnx_approx.min_weighted_vertex_cover(g))
    assert all(u in cover or v in cover for u, v in g.edges())
    # A maximum matching lower-bounds the optimum, so a 2-approx obeys
    # |cover| <= 2 * |matching|.
    matching = len(fnx.max_weight_matching(g, maxcardinality=True))
    assert len(cover) <= 2 * matching


@pytest.mark.parametrize("seed", range(40))
def test_clique_approximations_are_sound(seed):
    g, _, _ = _graph(seed)
    adj = {x: set(g.neighbors(x)) for x in g}
    clique = set(fnx_approx.max_clique(g))
    assert all(b in adj[a] for a in clique for b in clique if a != b)
    actual_max = max((len(c) for c in fnx.find_cliques(g)), default=0)
    assert fnx_approx.large_clique_size(g) <= actual_max


@pytest.mark.parametrize("seed", range(30))
def test_steiner_tree_spans_terminals(seed):
    g, ng, n = _graph(seed, p=0.5)
    if not nx.is_connected(ng) or n < 4:
        pytest.skip("disconnected or tiny")
    for u, v in g.edges():
        g[u][v]["weight"] = 1
    terminals = random.Random(seed).sample(range(n), 3)
    tree = fnx_approx.steiner_tree(g, terminals)
    assert all(t in tree.nodes() for t in terminals)
    if tree.number_of_nodes() > 0:
        assert tree.number_of_edges() == tree.number_of_nodes() - 1


@pytest.mark.parametrize("seed", range(20))
def test_tsp_returns_closed_tour(seed):
    rng = random.Random(seed)
    n = rng.randint(4, 7)
    g = fnx.complete_graph(n)
    for u, v in g.edges():
        g[u][v]["weight"] = rng.randint(1, 20)
    cycle = fnx_approx.traveling_salesman_problem(g, cycle=True)
    assert set(cycle[:-1]) == set(range(n))   # visits every node
    assert cycle[0] == cycle[-1]              # closed tour
