"""Directed local node connectivity parity (br-r37-c1-ebd8d).

The native directed local kernel undercounted node-independent paths for
some non-adjacent pairs — e.g. returning 1 where two node-disjoint s->t
paths exist (so Menger's #node_disjoint_paths and networkx both give 2).
The wrapper now delegates every directed local s-t query to nx; the
directed global path keeps the native kernel.
"""

from __future__ import annotations

import random

import pytest
import networkx as nx
import franken_networkx as fnx


def _digraph(seed, p=0.45):
    rng = random.Random(seed)
    n = rng.randint(4, 7)
    fg = fnx.DiGraph()
    ng = nx.DiGraph()
    fg.add_nodes_from(range(n))
    ng.add_nodes_from(range(n))
    for u in range(n):
        for v in range(n):
            if u != v and rng.random() < p:
                fg.add_edge(u, v)
                ng.add_edge(u, v)
    return fg, ng, n


@pytest.mark.parametrize("seed", range(60))
def test_directed_local_node_connectivity_matches_networkx(seed):
    fg, ng, n = _digraph(seed)
    for s in range(n):
        for t in range(n):
            if s == t:
                continue
            assert fnx.node_connectivity(fg, s, t) == nx.node_connectivity(ng, s, t)


@pytest.mark.parametrize("seed", range(60))
def test_directed_node_connectivity_satisfies_menger(seed):
    # node connectivity == number of node-disjoint s->t paths.
    fg, ng, n = _digraph(seed)
    for s in range(n):
        for t in range(n):
            if s == t:
                continue
            nc = fnx.node_connectivity(fg, s, t)
            try:
                path_count = len(list(fnx.node_disjoint_paths(fg, s, t)))
            except nx.NetworkXNoPath:
                path_count = 0
            assert nc == path_count


def test_regression_undercounted_pair():
    # The exact pair from the sweep: two node-disjoint paths 4->6 exist.
    edges = [
        (0, 1), (0, 3), (0, 5), (1, 0), (1, 2), (1, 3), (1, 4), (2, 3),
        (2, 6), (3, 1), (3, 2), (4, 1), (4, 3), (5, 0), (5, 2), (5, 3),
        (5, 6), (6, 0), (6, 1), (6, 2), (6, 4), (6, 5),
    ]
    fg = fnx.DiGraph(edges)
    ng = nx.DiGraph(edges)
    assert fnx.node_connectivity(fg, 4, 6) == 2
    assert fnx.node_connectivity(fg, 4, 6) == nx.node_connectivity(ng, 4, 6)


@pytest.mark.parametrize("seed", range(40))
def test_directed_global_node_connectivity_matches_networkx(seed):
    fg, ng, _ = _digraph(seed)
    assert fnx.node_connectivity(fg) == nx.node_connectivity(ng)
