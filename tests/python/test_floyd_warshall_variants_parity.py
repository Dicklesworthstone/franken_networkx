"""Differential parity for Floyd-Warshall variants.

Covers ``floyd_warshall_numpy`` (dense distance matrix) and
``floyd_warshall_predecessor_and_distance`` (predecessor + distance
dicts). Neither had a dedicated test file.

Graphs are oriented low->high index so they stay acyclic (no negative
cycle), keeping the all-pairs distances well-defined even with negative
edge weights.

br-r37-c1-hykcx
"""

from __future__ import annotations

import random

import numpy as np
import pytest
import networkx as nx
import franken_networkx as fnx


def _valid_pair(seed, negatives=True):
    rng = random.Random(seed)
    n = rng.randint(4, 8)
    fg = fnx.DiGraph()
    ng = nx.DiGraph()
    fg.add_nodes_from(range(n))
    ng.add_nodes_from(range(n))
    for u in range(n):
        for v in range(u + 1, n):  # acyclic -> no negative cycle
            if rng.random() < 0.5:
                w = rng.randint(-3, 9) if negatives else rng.randint(1, 9)
                fg.add_edge(u, v, weight=w)
                ng.add_edge(u, v, weight=w)
    return fg, ng, n


@pytest.mark.parametrize("seed", range(50))
def test_floyd_warshall_numpy_matches_networkx(seed):
    fg, ng, _ = _valid_pair(seed)
    assert np.allclose(
        np.asarray(fnx.floyd_warshall_numpy(fg)),
        np.asarray(nx.floyd_warshall_numpy(ng)),
        equal_nan=True,
    )


@pytest.mark.parametrize("seed", range(50))
def test_floyd_warshall_predecessor_and_distance_matches_networkx(seed):
    fg, ng, _ = _valid_pair(seed)
    _, fdist = fnx.floyd_warshall_predecessor_and_distance(fg)
    _, ndist = nx.floyd_warshall_predecessor_and_distance(ng)
    # Distances are the well-defined invariant; predecessor choices are not
    # unique when multiple shortest paths tie, so only distances are compared.
    assert {u: dict(d) for u, d in fdist.items()} == {
        u: dict(d) for u, d in ndist.items()
    }


def test_floyd_warshall_goldens():
    g = fnx.DiGraph()
    ng = nx.DiGraph()
    for u, v, w in [(0, 1, 1), (1, 2, 2), (0, 2, 5)]:
        g.add_edge(u, v, weight=w)
        ng.add_edge(u, v, weight=w)
    _, dist = fnx.floyd_warshall_predecessor_and_distance(g)
    # 0->1->2 (cost 3) beats the direct 0->2 (cost 5).
    assert dist[0][2] == 3
    assert {u: dict(d) for u, d in dist.items()} == {
        u: dict(d) for u, d in nx.floyd_warshall_predecessor_and_distance(ng)[1].items()
    }
