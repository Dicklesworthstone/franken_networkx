"""Differential + golden parity for labeled DFS and BFS/DFS pred/succ maps.

Covers ``dfs_labeled_edges`` (yields ``(u, v, direction)`` where direction
is forward/reverse/nontree) and the ``bfs_predecessors`` /
``bfs_successors`` / ``dfs_successors`` / ``dfs_predecessors`` maps. None
had a dedicated test file. All are order-deterministic.

br-r37-c1-w7wwr
"""

from __future__ import annotations

import random

import pytest
import networkx as nx
import franken_networkx as fnx


def _pair(seed, directed=False, p=0.4):
    rng = random.Random(seed)
    n = rng.randint(5, 9)
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
    return fg, ng


@pytest.mark.parametrize("directed", [False, True])
@pytest.mark.parametrize("seed", range(40))
def test_dfs_labeled_edges_matches_networkx(directed, seed):
    fg, ng = _pair(seed, directed=directed)
    assert list(fnx.dfs_labeled_edges(fg, 0)) == list(nx.dfs_labeled_edges(ng, 0))


@pytest.mark.parametrize(
    "fn", ["bfs_predecessors", "bfs_successors", "dfs_successors", "dfs_predecessors"]
)
@pytest.mark.parametrize("directed", [False, True])
@pytest.mark.parametrize("seed", range(30))
def test_pred_succ_maps_match_networkx(fn, directed, seed):
    fg, ng = _pair(seed, directed=directed)
    assert dict(getattr(fnx, fn)(fg, 0)) == dict(getattr(nx, fn)(ng, 0))


def test_goldens():
    g = fnx.Graph([(0, 1), (1, 2)])
    ng = nx.Graph([(0, 1), (1, 2)])
    assert list(fnx.dfs_labeled_edges(g, 0)) == list(nx.dfs_labeled_edges(ng, 0))
    assert dict(fnx.bfs_successors(g, 0)) == {0: [1], 1: [2]}
    assert dict(fnx.dfs_predecessors(g, 0)) == {1: 0, 2: 1}
