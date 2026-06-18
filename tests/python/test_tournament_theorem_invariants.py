"""Oracle-free tournament theorem-invariants.

Complements the differential tournament test with relations that hold by
theorem:

* a fully oriented graph (one arc per pair) is a tournament
* Rédei's theorem: every tournament has a Hamiltonian path
* the score sequence is non-decreasing and sums to n(n-1)/2 (one win per
  pair)
* ``is_reachable`` is reflexive, and a strongly connected tournament has
  every node reachable from every other

br-r37-c1-g4bxy
"""

from __future__ import annotations

import random

import pytest
import franken_networkx as fnx
from franken_networkx.algorithms import tournament as fnx_tournament


def _random_tournament(seed):
    rng = random.Random(seed)
    n = rng.randint(3, 8)
    g = fnx.DiGraph()
    g.add_nodes_from(range(n))
    for u in range(n):
        for v in range(u + 1, n):
            if rng.random() < 0.5:
                g.add_edge(u, v)
            else:
                g.add_edge(v, u)
    return g, n


@pytest.mark.parametrize("seed", range(60))
def test_is_tournament_and_redei_hamiltonian_path(seed):
    g, n = _random_tournament(seed)
    assert fnx_tournament.is_tournament(g)
    # Rédei: every tournament contains a Hamiltonian path.
    path = fnx_tournament.hamiltonian_path(g)
    assert len(path) == n
    assert len(set(path)) == n
    assert all(g.has_edge(path[i], path[i + 1]) for i in range(n - 1))


@pytest.mark.parametrize("seed", range(60))
def test_score_sequence_properties(seed):
    g, n = _random_tournament(seed)
    scores = fnx_tournament.score_sequence(g)
    assert scores == sorted(scores)               # non-decreasing
    assert sum(scores) == n * (n - 1) // 2         # one win per pair
    assert len(scores) == n


@pytest.mark.parametrize("seed", range(40))
def test_reachability_consistency(seed):
    g, n = _random_tournament(seed)
    # Reachability is reflexive.
    for v in range(n):
        assert fnx_tournament.is_reachable(g, v, v)
    # In a strongly connected tournament every node reaches every other.
    if fnx_tournament.is_strongly_connected(g):
        for s in range(n):
            for t in range(n):
                assert fnx_tournament.is_reachable(g, s, t)
