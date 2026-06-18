"""Differential + golden parity for ``number_of_walks``.

``number_of_walks(G, walk_length)`` returns a nested dict counting the
walks of the given length between every ordered node pair (the entries of
``A**walk_length``). No dedicated test file existed.

br-r37-c1-rkct7
"""

from __future__ import annotations

import random

import pytest
import networkx as nx
import franken_networkx as fnx


def _pair(seed, directed=False, p=0.4):
    rng = random.Random(seed)
    n = rng.randint(4, 8)
    fnx_cls, nx_cls = (fnx.DiGraph, nx.DiGraph) if directed else (fnx.Graph, nx.Graph)
    fg = fnx_cls()
    ng = nx_cls()
    fg.add_nodes_from(range(n))
    ng.add_nodes_from(range(n))
    for u in range(n):
        for v in range(n):
            if u != v and (directed or u < v) and rng.random() < p:
                fg.add_edge(u, v)
                ng.add_edge(u, v)
    return fg, ng, n


def _nested(d):
    return {a: dict(b) for a, b in d.items()}


@pytest.mark.parametrize("directed", [False, True])
@pytest.mark.parametrize("walk_length", [0, 1, 2, 3])
@pytest.mark.parametrize("seed", range(25))
def test_number_of_walks_matches_networkx(directed, walk_length, seed):
    fg, ng, _ = _pair(seed, directed=directed)
    assert _nested(fnx.number_of_walks(fg, walk_length)) == _nested(
        nx.number_of_walks(ng, walk_length)
    )


def test_number_of_walks_invariants():
    fg, _, n = _pair(3)
    # length 0: identity (1 on the diagonal, 0 elsewhere).
    w0 = fnx.number_of_walks(fg, 0)
    assert all(w0[u][v] == (1 if u == v else 0) for u in range(n) for v in range(n))
    # length 1: the adjacency matrix.
    w1 = fnx.number_of_walks(fg, 1)
    assert all(
        w1[u][v] == (1 if fg.has_edge(u, v) else 0)
        for u in range(n) for v in range(n)
    )


def test_number_of_walks_golden():
    # Triangle: two length-2 walks from a node back to itself (via each other).
    g = fnx.Graph([(0, 1), (1, 2), (2, 0)])
    ng = nx.Graph([(0, 1), (1, 2), (2, 0)])
    assert fnx.number_of_walks(g, 2)[0][0] == 2
    assert _nested(fnx.number_of_walks(g, 2)) == _nested(nx.number_of_walks(ng, 2))
