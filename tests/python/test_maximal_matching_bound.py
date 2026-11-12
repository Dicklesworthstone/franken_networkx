"""maximal_matching validity + 2-approximation bound.

A maximal matching (greedy, no edge can be added) is a 2-approximation of the
maximum matching. These cross-check maximal_matching against max_weight_matching:
  - maximal_matching is a valid matching (no shared endpoints);
  - it is maximal (no unmatched edge could be added);
  - its size is at least half the maximum matching size (2-approximation);
  - its size is at most the maximum matching size, and at most floor(n/2).
Oracle-free, independent of networkx.

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
def test_maximal_matching_is_valid_and_maximal(seed):
    g, n = _graph(seed)
    if g.number_of_edges() == 0:
        pytest.skip("no edges")
    mm = fnx.maximal_matching(g)

    # Valid matching: no shared endpoints.
    matched = set()
    for u, v in mm:
        # Disjointness and maximality are both satisfiable by pairs that are not
        # edges at all — {(0,2)} on a 4-cycle passes both — so pin membership.
        assert g.has_edge(u, v)
        assert u not in matched and v not in matched
        matched.add(u); matched.add(v)
    # Maximal: no edge with both endpoints unmatched.
    for u, v in g.edges():
        assert u in matched or v in matched
    # A matching covers 2 nodes per edge, so it cannot exceed floor(n/2).
    assert len(mm) <= n // 2


@pytest.mark.parametrize("seed", range(40))
def test_maximal_matching_two_approximation(seed):
    g, n = _graph(seed)
    if g.number_of_edges() == 0:
        pytest.skip("no edges")
    mm_size = len(fnx.maximal_matching(g))
    max_size = len(fnx.max_weight_matching(g))
    # 2-approximation: maximum/2 <= maximal <= maximum.
    assert mm_size >= max_size / 2 - 1e-9
    assert mm_size <= max_size
    # A matching can cover at most floor(n/2) pairs.
    assert max_size <= n // 2


def test_two_approximation_is_tight_not_merely_satisfied():
    """A witness attaining the bound exactly, so `>= maximum/2` is not vacuous.

    Insert the middle edge of a 4-path first: greedy takes it and blocks both end
    edges, giving a maximal matching of 1 against a maximum of 2 — exactly half.
    """
    g = fnx.Graph(); g.add_edges_from([(1, 2), (0, 1), (2, 3)])
    maximal, maximum = len(fnx.maximal_matching(g)), len(fnx.max_weight_matching(g))
    assert (maximal, maximum) == (1, 2)
    assert maximal == maximum / 2                      # the bound is attained

    # Same construction one path longer: 2 against 3, still within the bound.
    h = fnx.Graph(); h.add_edges_from([(1, 2), (0, 1), (2, 3), (4, 5), (3, 4)])
    assert (len(fnx.maximal_matching(h)), len(fnx.max_weight_matching(h))) == (2, 3)


def test_random_family_exercises_the_strict_case():
    """Guards the sweep: the bound says nothing where maximal == maximum."""
    strict = 0
    for seed in range(40):
        g, _ = _graph(seed)
        if g.number_of_edges() == 0:
            continue
        if len(fnx.maximal_matching(g)) < len(fnx.max_weight_matching(g)):
            strict += 1
    # Measured 9 of 40; assert a floor so the family cannot drift to all-equal,
    # where the 2-approximation would hold trivially on every draw.
    assert strict >= 5, f"only {strict} draws have maximal < maximum"


def test_perfect_matching_on_even_complete():
    # K_{2m} has a perfect matching of size m.
    for m in (2, 3):
        g = fnx.complete_graph(2 * m)
        assert len(fnx.max_weight_matching(g)) == m
        assert len(fnx.maximal_matching(g)) == m  # K_n: any maximal matching is perfect
