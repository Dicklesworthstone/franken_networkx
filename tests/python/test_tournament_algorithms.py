"""Tournament algorithm parity + Hamiltonian-path validity invariant.

A tournament is an orientation of a complete graph (exactly one arc per pair).
By Redei's theorem every tournament has a Hamiltonian path, so the returned
path must be VALID — use every node once, with each consecutive pair connected
by an arc. This oracle-free invariant plus networkx parity (is_tournament,
score_sequence, is_strongly_connected) pins the module.

No mocks: real fnx and real networkx on random tournaments.
"""

from __future__ import annotations

import random

import pytest
import networkx as nx
import franken_networkx as fnx
from franken_networkx.algorithms import tournament as ft
from networkx.algorithms import tournament as nt


def _tournament(seed):
    r = random.Random(seed)
    n = r.randint(4, 8)
    edges = []
    for u in range(n):
        for v in range(u + 1, n):
            edges.append((u, v) if r.random() < 0.5 else (v, u))
    return fnx.DiGraph(edges), nx.DiGraph(edges), n


@pytest.mark.parametrize("seed", range(40))
def test_is_tournament_and_score_sequence_parity(seed):
    fg, ng, n = _tournament(seed)
    assert ft.is_tournament(fg) == nt.is_tournament(ng)
    assert ft.score_sequence(fg) == nt.score_sequence(ng)
    assert ft.is_strongly_connected(fg) == nt.is_strongly_connected(ng)
    # Score sequence is the sorted out-degree sequence; sums to C(n, 2).
    assert sum(ft.score_sequence(fg)) == n * (n - 1) // 2


@pytest.mark.parametrize("seed", range(40))
def test_hamiltonian_path_is_valid(seed):
    fg, ng, n = _tournament(seed)
    hp = ft.hamiltonian_path(fg)
    # Uses every node exactly once.
    assert len(hp) == n
    assert set(hp) == set(range(n))
    # Each consecutive pair is connected by an arc (the path is real).
    assert all(fg.has_edge(hp[i], hp[i + 1]) for i in range(n - 1))


def test_non_tournament_is_rejected():
    # A graph missing an arc between a pair is not a tournament.
    g = fnx.DiGraph([(0, 1), (1, 2)])  # 0-2 pair has no arc
    ng = nx.DiGraph([(0, 1), (1, 2)])
    assert ft.is_tournament(g) == nt.is_tournament(ng) is False
