"""Oracle-free structural invariants for coloring / clique / matching.

These assert properties that must hold by definition or theorem, without
using networkx as an oracle — they catch bugs that a fnx-vs-nx diff cannot
(e.g. both libraries agreeing on a wrong-but-consistent value).

br-r37-c1-sg1e2
"""

from __future__ import annotations

import random

import pytest
import networkx as nx
import franken_networkx as fnx
from franken_networkx.algorithms import bipartite as fnx_bip

_STRATEGIES = [
    "largest_first",
    "smallest_last",
    "random_sequential",
    "saturation_largest_first",
    "connected_sequential_bfs",
    "connected_sequential_dfs",
    "independent_set",
]


def _random_graph(seed, p=0.4):
    rng = random.Random(seed)
    n = rng.randint(5, 10)
    g = fnx.Graph()
    g.add_nodes_from(range(n))
    for u in range(n):
        for v in range(u + 1, n):
            if rng.random() < p:
                g.add_edge(u, v)
    return g, n


def _max_clique_size(g):
    return max((len(c) for c in fnx.find_cliques(g)), default=1)


@pytest.mark.parametrize("strategy", _STRATEGIES)
@pytest.mark.parametrize("seed", range(20))
def test_greedy_color_is_proper_and_respects_clique_bound(strategy, seed):
    g, _ = _random_graph(seed)
    coloring = fnx.greedy_color(g, strategy=strategy)
    # Proper: no edge joins two equally-coloured endpoints.
    assert all(coloring[u] != coloring[v] for u, v in g.edges())
    # A proper colouring needs at least as many colours as the largest clique.
    n_colors = len(set(coloring.values())) if coloring else 0
    assert n_colors >= _max_clique_size(g)


@pytest.mark.parametrize("seed", range(40))
def test_matchings_are_valid(seed):
    g, _ = _random_graph(seed)
    for matching in (fnx.max_weight_matching(g), fnx.maximal_matching(g)):
        seen = set()
        for u, v in matching:
            assert g.has_edge(u, v)
            assert u not in seen and v not in seen
            seen.add(u)
            seen.add(v)


@pytest.mark.parametrize("seed", range(40))
def test_handshaking_lemma(seed):
    g, _ = _random_graph(seed)
    assert sum(d for _, d in g.degree()) == 2 * g.number_of_edges()


@pytest.mark.parametrize("seed", range(30))
def test_konig_bipartite_matching_equals_vertex_cover(seed):
    rng = random.Random(seed)
    n = rng.randint(4, 9)
    top = list(range(n // 2))
    bot = list(range(n // 2, n))
    g = fnx.Graph()
    g.add_nodes_from(top, bipartite=0)
    g.add_nodes_from(bot, bipartite=1)
    for u in top:
        for v in bot:
            if rng.random() < 0.4:
                g.add_edge(u, v)
    if g.number_of_edges() == 0:
        pytest.skip("no edges")
    matching = fnx_bip.maximum_matching(g, top_nodes=top)
    cover = fnx_bip.to_vertex_cover(g, matching, top_nodes=top)
    # König's theorem: |maximum matching| == |minimum vertex cover|.
    assert len(matching) // 2 == len(cover)
