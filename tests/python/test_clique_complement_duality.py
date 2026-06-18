"""Clique enumeration parity + clique/independent-set complement duality.

Cliques and independent sets are dual under graph complement:
  - a CLIQUE in G is an INDEPENDENT SET in the complement of G (no edge of the
    complement lies inside it), and
  - the independence number alpha(G) equals the clique number of the complement,
    omega(complement(G)).
These oracle-free dualities, plus find_cliques parity (set/count) with networkx,
pin the clique machinery and the complement operation jointly.

No mocks: real fnx and real networkx.
"""

from __future__ import annotations

import random

import pytest
import networkx as nx
import franken_networkx as fnx


def _graph(seed):
    r = random.Random(seed)
    n = r.randint(5, 9)
    edges = [(u, v) for u in range(n) for v in range(u + 1, n) if r.random() < 0.45]
    fg = fnx.Graph(); fg.add_nodes_from(range(n)); fg.add_edges_from(edges)
    ng = nx.Graph(); ng.add_nodes_from(range(n)); ng.add_edges_from(edges)
    return fg, ng, n


def _cliques_sorted(g):
    return sorted(sorted(c) for c in fnx.find_cliques(g))


@pytest.mark.parametrize("seed", range(40))
def test_find_cliques_parity(seed):
    fg, ng, n = _graph(seed)
    assert _cliques_sorted(fg) == sorted(sorted(c) for c in nx.find_cliques(ng))
    # Clique number and number of maximal cliques match networkx.
    assert max((len(c) for c in fnx.find_cliques(fg)), default=0) == (
        max((len(c) for c in nx.find_cliques(ng)), default=0)
    )
    assert sum(1 for _ in fnx.find_cliques(fg)) == sum(1 for _ in nx.find_cliques(ng))


@pytest.mark.parametrize("seed", range(40))
def test_clique_is_independent_set_in_complement(seed):
    fg, ng, n = _graph(seed)
    comp = fnx.complement(fg)
    # Every maximal clique of G is an independent set in the complement.
    for clique in fnx.find_cliques(fg):
        for i, u in enumerate(clique):
            for w in clique[i + 1:]:
                assert not comp.has_edge(u, w)


@pytest.mark.parametrize("seed", range(40))
def test_independence_number_equals_complement_clique_number(seed):
    fg, ng, n = _graph(seed)
    comp = fnx.complement(fg)
    # alpha(G) = omega(complement(G)): independence number via complement cliques.
    alpha = max((len(c) for c in fnx.find_cliques(comp)), default=0)
    alpha_nx = max((len(c) for c in nx.find_cliques(nx.complement(ng))), default=0)
    assert alpha == alpha_nx
