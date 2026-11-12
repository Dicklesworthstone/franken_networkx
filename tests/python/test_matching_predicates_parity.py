"""Differential + golden parity for matching predicates.

Covers ``is_matching``, ``is_maximal_matching`` and
``is_perfect_matching`` (boolean validators over a candidate matching),
plus ``min_weight_matching`` total-weight optimality. The predicates had
little/no dedicated coverage.

br-r37-c1-hjiql
"""

from __future__ import annotations

import random

import pytest
import networkx as nx
import franken_networkx as fnx


def _pair(seed, p=0.5):
    rng = random.Random(seed)
    n = 2 * rng.randint(2, 5)
    fg = fnx.Graph()
    ng = nx.Graph()
    fg.add_nodes_from(range(n))
    ng.add_nodes_from(range(n))
    for u in range(n):
        for v in range(u + 1, n):
            if rng.random() < p:
                fg.add_edge(u, v)
                ng.add_edge(u, v)
    return fg, ng, n


@pytest.mark.parametrize("fn", ["is_matching", "is_maximal_matching", "is_perfect_matching"])
@pytest.mark.parametrize("seed", range(50))
def test_predicate_matches_networkx_on_real_matching(fn, seed):
    fg, ng, _ = _pair(seed)
    matching = nx.maximal_matching(ng)  # a genuine matching
    assert getattr(fnx, fn)(fg, matching) == getattr(nx, fn)(ng, matching)


@pytest.mark.parametrize("seed", range(40))
def test_is_matching_rejects_invalid_like_networkx(seed):
    fg, ng, n = _pair(seed)
    rng = random.Random(seed * 11 + 1)
    # A random set of node pairs — usually NOT a valid matching (shared nodes).
    candidate = {
        (u, v)
        for u in range(n)
        for v in range(u + 1, n)
        if rng.random() < 0.3
    }
    assert fnx.is_matching(fg, candidate) == nx.is_matching(ng, candidate)


def test_matching_predicate_goldens():
    c4 = fnx.cycle_graph(4)
    assert fnx.is_perfect_matching(c4, {(0, 1), (2, 3)})
    assert not fnx.is_matching(c4, {(0, 1), (1, 2)})        # shares node 1
    assert not fnx.is_maximal_matching(fnx.path_graph(4), {(0, 1)})  # (2,3) free
    # dict form is accepted by is_matching.
    assert fnx.is_matching(c4, {0: 1, 1: 0, 2: 3, 3: 2})


@pytest.mark.parametrize("seed", range(30))
def test_min_weight_matching_total_weight_matches_networkx(seed):
    rng = random.Random(seed + 7)
    n = 2 * rng.randint(2, 5)
    fg = fnx.Graph()
    ng = nx.Graph()
    fg.add_nodes_from(range(n))
    ng.add_nodes_from(range(n))
    for u in range(n):
        for v in range(u + 1, n):
            if rng.random() < 0.5:
                w = rng.randint(1, 9)
                fg.add_edge(u, v, weight=w)
                ng.add_edge(u, v, weight=w)
    fm = fnx.min_weight_matching(fg)
    nm = nx.min_weight_matching(ng)
    # Optimal matching is not unique; total weight is the invariant.
    fw = sum(fg[u][v]["weight"] for u, v in fm)
    nw = sum(ng[u][v]["weight"] for u, v in nm)
    assert fw == nw
