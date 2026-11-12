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


@pytest.mark.parametrize("seed", range(60))
def test_score_sequence_holds_the_actual_out_degrees(seed):
    """Sorted, right length, right total — and none of that fixes the VALUES.

    A score sequence is the sorted out-degrees. Moving one win from the top
    score to the bottom keeps it sorted, keeps the length, and keeps the total
    at C(n,2); such a different-but-passing sequence exists on 49 of these 60
    draws. Comparing against the out-degrees pins the values themselves.
    """
    g, _ = _random_tournament(seed)
    assert list(fnx_tournament.score_sequence(g)) == sorted(d for _, d in g.out_degree())


def test_non_tournaments_are_rejected():
    """is_tournament is only ever asked about graphs that ARE tournaments."""
    # A pair with no arc between them.
    missing = fnx.DiGraph([(0, 1), (1, 2)])
    missing.add_nodes_from([0, 1, 2])
    # A pair with arcs both ways.
    both_ways = fnx.DiGraph([(0, 1), (1, 0), (1, 2), (0, 2)])

    assert fnx_tournament.is_tournament(missing) is False
    assert fnx_tournament.is_tournament(both_ways) is False
    # ...and a real tournament still passes, so the predicate is not constant.
    g, _ = _random_tournament(0)
    assert fnx_tournament.is_tournament(g) is True


@pytest.mark.parametrize("seed", range(40))
def test_non_strongly_connected_tournaments_have_an_unreachable_pair(seed):
    """The reachability test asserts only the strongly-connected direction.

    Its `if is_strongly_connected` branch says nothing about the other case,
    which is where is_reachable could wrongly return True for everything.
    """
    g, n = _random_tournament(seed)
    if fnx_tournament.is_strongly_connected(g):
        pytest.skip("strongly connected — covered by the sweep above")

    assert any(
        not fnx_tournament.is_reachable(g, a, b)
        for a in range(n)
        for b in range(n)
    )
