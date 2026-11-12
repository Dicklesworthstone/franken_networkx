"""Differential + golden parity for ``kemeny_constant``.

The Kemeny constant (expected random-walk hitting time, weighted by the
stationary distribution) for a connected graph. No dedicated test file
existed.

br-r37-c1-2iil4
"""

from __future__ import annotations

import random

import pytest
import networkx as nx
import franken_networkx as fnx


def _connected(seed, weighted=False, p=0.4):
    rng = random.Random(seed)
    n = rng.randint(5, 10)
    p_cur = p
    for _ in range(60):
        fg = fnx.Graph()
        ng = nx.Graph()
        fg.add_nodes_from(range(n))
        ng.add_nodes_from(range(n))
        for u in range(n):
            for v in range(u + 1, n):
                if rng.random() < p_cur:
                    if weighted:
                        w = round(rng.uniform(1, 4), 2)
                        fg.add_edge(u, v, weight=w)
                        ng.add_edge(u, v, weight=w)
                    else:
                        fg.add_edge(u, v)
                        ng.add_edge(u, v)
        if nx.is_connected(ng):
            return fg, ng, n
        p_cur = min(0.9, p_cur + 0.05)
    return None


@pytest.mark.parametrize("weighted", [False, True])
@pytest.mark.parametrize("seed", range(40))
def test_kemeny_constant_matches_networkx(weighted, seed):
    pair = _connected(seed, weighted=weighted)
    if pair is None:
        pytest.skip("no connected graph")
    fg, ng, _ = pair
    kwargs = {"weight": "weight"} if weighted else {"weight": None}
    assert fnx.kemeny_constant(fg, **kwargs) == pytest.approx(
        nx.kemeny_constant(ng, **kwargs), rel=1e-7
    )


@pytest.mark.parametrize("n", [3, 4, 5, 6])
def test_complete_graph_golden(n):
    # The Kemeny constant of K_n is (n - 1)**2 / n.
    value = fnx.kemeny_constant(fnx.complete_graph(n))
    assert value == pytest.approx((n - 1) ** 2 / n)
    assert value == pytest.approx(nx.kemeny_constant(nx.complete_graph(n)))


def test_disconnected_raises_like_networkx():
    fg = fnx.Graph([(0, 1), (2, 3)])
    ng = nx.Graph([(0, 1), (2, 3)])
    with pytest.raises(nx.NetworkXError):
        fnx.kemeny_constant(fg)
    with pytest.raises(nx.NetworkXError):
        nx.kemeny_constant(ng)
