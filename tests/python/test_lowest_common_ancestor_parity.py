"""Differential + golden parity for lowest-common-ancestor functions.

Covers ``lowest_common_ancestor``, ``all_pairs_lowest_common_ancestor``
(DAG) and ``tree_all_pairs_lowest_common_ancestor`` (tree). The
all-pairs variants had no dedicated test file.

br-r37-c1-i11v4
"""

from __future__ import annotations

import random

import pytest
import networkx as nx
import franken_networkx as fnx


def _random_dag(seed):
    rng = random.Random(seed)
    n = rng.randint(4, 9)
    fg = fnx.DiGraph()
    ng = nx.DiGraph()
    fg.add_nodes_from(range(n))
    ng.add_nodes_from(range(n))
    for v in range(1, n):
        for _ in range(rng.randint(1, 2)):
            u = rng.randint(0, v - 1)
            fg.add_edge(u, v)
            ng.add_edge(u, v)
    return fg, ng, n


def _random_tree(seed):
    rng = random.Random(seed * 7 + 1)
    n = rng.randint(3, 9)
    fg = fnx.DiGraph()
    ng = nx.DiGraph()
    fg.add_nodes_from(range(n))
    ng.add_nodes_from(range(n))
    for v in range(1, n):
        u = rng.randint(0, v - 1)
        fg.add_edge(u, v)
        ng.add_edge(u, v)
    return fg, ng, n


def _norm(pairs):
    return {tuple(sorted(k)): v for k, v in dict(pairs).items()}


@pytest.mark.parametrize("seed", range(50))
def test_all_pairs_lowest_common_ancestor_matches_networkx(seed):
    fg, ng, _ = _random_dag(seed)
    assert _norm(fnx.all_pairs_lowest_common_ancestor(fg)) == _norm(
        nx.all_pairs_lowest_common_ancestor(ng)
    )


@pytest.mark.parametrize("seed", range(40))
def test_all_pairs_with_explicit_pairs_matches_networkx(seed):
    fg, ng, n = _random_dag(seed)
    rng = random.Random(seed * 11 + 3)
    pairs = [(rng.randrange(n), rng.randrange(n)) for _ in range(4)]
    assert dict(fnx.all_pairs_lowest_common_ancestor(fg, pairs=pairs)) == dict(
        nx.all_pairs_lowest_common_ancestor(ng, pairs=pairs)
    )


@pytest.mark.parametrize("seed", range(40))
def test_tree_all_pairs_lowest_common_ancestor_matches_networkx(seed):
    fg, ng, _ = _random_tree(seed)
    assert _norm(fnx.tree_all_pairs_lowest_common_ancestor(fg)) == _norm(
        nx.tree_all_pairs_lowest_common_ancestor(ng)
    )


def test_lca_goldens():
    # Binary tree: 0 -> {1, 2}, 1 -> {3, 4}.
    g = fnx.DiGraph([(0, 1), (0, 2), (1, 3), (1, 4)])
    assert fnx.lowest_common_ancestor(g, 3, 4) == 1
    assert fnx.lowest_common_ancestor(g, 3, 2) == 0
    assert fnx.lowest_common_ancestor(g, 0, 4) == 0


def test_cyclic_graph_raises_like_networkx():
    fg = fnx.DiGraph([(0, 1), (1, 0)])
    ng = nx.DiGraph([(0, 1), (1, 0)])
    with pytest.raises(nx.NetworkXError):
        dict(fnx.all_pairs_lowest_common_ancestor(fg))
    with pytest.raises(nx.NetworkXError):
        dict(nx.all_pairs_lowest_common_ancestor(ng))
