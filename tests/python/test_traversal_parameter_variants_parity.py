"""Differential parity for less-tested traversal parameters.

Default BFS/DFS traversal is covered elsewhere; this exercises the
``depth_limit`` and ``sort_neighbors`` knobs, which drive distinct
code paths (bounded frontier expansion and custom neighbour ordering).

br-r37-c1-psecs
"""

from __future__ import annotations

import random

import pytest
import networkx as nx
import franken_networkx as fnx


def _pair(seed, directed=False, p=0.4):
    rng = random.Random(seed)
    n = rng.randint(6, 11)
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


def _reverse_sort(nbrs):
    return sorted(nbrs, reverse=True)


@pytest.mark.parametrize("directed", [False, True])
@pytest.mark.parametrize("depth_limit", [1, 2, 3])
@pytest.mark.parametrize("seed", range(20))
def test_depth_limited_traversal(directed, depth_limit, seed):
    fg, ng = _pair(seed, directed=directed)
    assert list(fnx.bfs_edges(fg, 0, depth_limit=depth_limit)) == list(
        nx.bfs_edges(ng, 0, depth_limit=depth_limit)
    )
    assert list(fnx.dfs_edges(fg, 0, depth_limit=depth_limit)) == list(
        nx.dfs_edges(ng, 0, depth_limit=depth_limit)
    )
    assert sorted(fnx.bfs_tree(fg, 0, depth_limit=depth_limit).edges()) == sorted(
        nx.bfs_tree(ng, 0, depth_limit=depth_limit).edges()
    )


@pytest.mark.parametrize("directed", [False, True])
@pytest.mark.parametrize("seed", range(30))
def test_sort_neighbors_traversal(directed, seed):
    fg, ng = _pair(seed, directed=directed)
    assert list(fnx.bfs_edges(fg, 0, sort_neighbors=_reverse_sort)) == list(
        nx.bfs_edges(ng, 0, sort_neighbors=_reverse_sort)
    )
    assert list(fnx.dfs_edges(fg, 0, sort_neighbors=_reverse_sort)) == list(
        nx.dfs_edges(ng, 0, sort_neighbors=_reverse_sort)
    )
