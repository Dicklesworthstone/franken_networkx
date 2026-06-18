"""Differential + golden parity for ``all_simple_edge_paths`` / ``is_simple_path``.

``all_simple_edge_paths(G, source, target, cutoff=...)`` yields every
simple path as a list of edges (deterministic order); ``is_simple_path``
validates a node sequence. Neither had a dedicated test file.

br-r37-c1-jzi48
"""

from __future__ import annotations

import random

import pytest
import networkx as nx
import franken_networkx as fnx


def _pair(seed, directed=False, p=0.45):
    rng = random.Random(seed)
    n = rng.randint(5, 8)
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


def _edge_paths(it):
    return [list(map(tuple, path)) for path in it]


@pytest.mark.parametrize("directed", [False, True])
@pytest.mark.parametrize("cutoff", [None, 1, 2, 3])
@pytest.mark.parametrize("seed", range(25))
def test_all_simple_edge_paths_matches_networkx(directed, cutoff, seed):
    fg, ng, n = _pair(seed, directed=directed)
    assert _edge_paths(
        fnx.all_simple_edge_paths(fg, 0, n - 1, cutoff=cutoff)
    ) == _edge_paths(nx.all_simple_edge_paths(ng, 0, n - 1, cutoff=cutoff))


@pytest.mark.parametrize("directed", [False, True])
@pytest.mark.parametrize("seed", range(40))
def test_is_simple_path_matches_networkx(directed, seed):
    fg, ng, n = _pair(seed, directed=directed)
    rng = random.Random(seed * 9 + 1)
    for _ in range(5):
        seq = [rng.randrange(n) for _ in range(rng.randint(0, 4))]
        assert fnx.is_simple_path(fg, seq) == nx.is_simple_path(ng, seq)


def test_is_simple_path_goldens():
    g = fnx.Graph([(0, 1), (1, 2), (2, 3)])
    assert fnx.is_simple_path(g, [0, 1, 2, 3])     # valid path
    assert not fnx.is_simple_path(g, [0, 1, 0])    # repeated node
    assert not fnx.is_simple_path(g, [0, 2])       # no such edge
    assert fnx.is_simple_path(g, [0])              # single node is simple
    assert not fnx.is_simple_path(g, [])           # empty is not


def test_all_simple_edge_paths_golden():
    g = fnx.Graph([(0, 1), (1, 2), (2, 3)])
    assert _edge_paths(fnx.all_simple_edge_paths(g, 0, 3)) == [
        [(0, 1), (1, 2), (2, 3)]
    ]
