"""Differential + golden parity for ``voterank``.

``voterank(G, number_of_nodes=...)`` returns a ranked list of influential
nodes via the VoteRank algorithm. The result order is deterministic, so
this compares the exact list. No dedicated test file existed.

br-r37-c1-5ll04
"""

from __future__ import annotations

import random

import pytest
import networkx as nx
import franken_networkx as fnx


def _pair(seed, directed=False, p=0.35):
    rng = random.Random(seed)
    n = rng.randint(6, 12)
    fnx_cls, nx_cls = (fnx.DiGraph, nx.DiGraph) if directed else (fnx.Graph, nx.Graph)
    fg = fnx_cls()
    ng = nx_cls()
    fg.add_nodes_from(range(n))
    ng.add_nodes_from(range(n))
    for u in range(n):
        for v in range(n):
            if u == v:
                continue
            if (directed or u < v) and rng.random() < p:
                fg.add_edge(u, v)
                ng.add_edge(u, v)
    return fg, ng, n


@pytest.mark.parametrize("directed", [False, True])
@pytest.mark.parametrize("seed", range(40))
def test_voterank_matches_networkx(directed, seed):
    fg, ng, _ = _pair(seed, directed=directed)
    assert list(fnx.voterank(fg)) == list(nx.voterank(ng))


@pytest.mark.parametrize("seed", range(30))
def test_voterank_number_of_nodes_matches_networkx(seed):
    fg, ng, n = _pair(seed)
    k = random.Random(seed * 3 + 1).randint(1, n)
    assert list(fnx.voterank(fg, number_of_nodes=k)) == list(
        nx.voterank(ng, number_of_nodes=k)
    )


def test_voterank_goldens():
    # Star center is the single most influential node.
    assert list(fnx.voterank(fnx.star_graph(5))) == [0]
    assert list(fnx.voterank(fnx.star_graph(5))) == list(nx.voterank(nx.star_graph(5)))
    # Empty graph yields no ranked nodes.
    assert list(fnx.voterank(fnx.Graph())) == list(nx.voterank(nx.Graph())) == []
