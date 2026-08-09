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

import itertools
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


def _brute_independence_number(g):
    """alpha(G) by exhaustive search — no clique machinery involved.

    The duality below relates alpha(G) to omega(complement(G)); computing the
    left side with find_cliques would make it a restatement rather than a test.
    """
    nodes = sorted(g.nodes())
    for size in range(len(nodes), 0, -1):
        for subset in itertools.combinations(nodes, size):
            if all(not g.has_edge(u, v) for u, v in itertools.combinations(subset, 2)):
                return size
    return 0


@pytest.mark.parametrize("seed", range(40))
def test_returned_cliques_are_cliques_and_are_maximal(seed):
    """find_cliques promises MAXIMAL cliques; only the clique half was implied.

    The existing duality test reaches the clique property through the
    complement, so a find_cliques and a complement that were wrong together
    would still satisfy it. This checks membership in G directly, and adds
    maximality, which nothing here asserted at all.
    """
    fg, _, _ = _graph(seed)
    cliques = [list(c) for c in fnx.find_cliques(fg)]
    nodes = set(fg.nodes())

    covered = set()
    for clique in cliques:
        assert set(clique) <= nodes
        # A clique: every pair adjacent IN G, checked without the complement.
        for u, v in itertools.combinations(clique, 2):
            assert fg.has_edge(u, v)
        # Maximal: no outside node is adjacent to all of it, so it cannot grow.
        for outsider in nodes - set(clique):
            assert not all(fg.has_edge(outsider, u) for u in clique)
        covered |= set(clique)

    # Every node lies in at least one maximal clique (an isolated node forms one).
    assert covered == nodes


@pytest.mark.parametrize("seed", range(40))
def test_independence_number_duality_against_an_independent_alpha(seed):
    """alpha(G) == omega(complement(G)), with alpha computed independently.

    The sibling test compares omega(complement) as computed by fnx against
    omega(complement) as computed by networkx — the same quantity twice, which
    is a parity check rather than the duality it is named for.
    """
    fg, _, _ = _graph(seed)
    alpha = _brute_independence_number(fg)
    omega_of_complement = max((len(c) for c in fnx.find_cliques(fnx.complement(fg))), default=0)
    assert alpha == omega_of_complement
