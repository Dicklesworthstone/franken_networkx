"""Differential + golden parity for tree/forest/branching predicates.

Covers ``is_tree``, ``is_forest`` (undirected and directed) and the
directed ``is_branching`` / ``is_arborescence``. None had a dedicated
test file.

br-r37-c1-xy5c1
"""

from __future__ import annotations

import random

import pytest
import networkx as nx
import franken_networkx as fnx


def _random_tree(seed, directed):
    rng = random.Random(seed)
    n = rng.randint(3, 8)
    fnx_cls, nx_cls = (fnx.DiGraph, nx.DiGraph) if directed else (fnx.Graph, nx.Graph)
    fg = fnx_cls()
    ng = nx_cls()
    fg.add_nodes_from(range(n))
    ng.add_nodes_from(range(n))
    for v in range(1, n):
        u = rng.randint(0, v - 1)
        fg.add_edge(u, v)
        ng.add_edge(u, v)
    return fg, ng


def _random_graph(seed, directed, p=0.3):
    rng = random.Random(seed * 31 + 1)
    n = rng.randint(3, 8)
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


@pytest.mark.parametrize("fn", ["is_tree", "is_forest"])
@pytest.mark.parametrize("directed", [False, True])
@pytest.mark.parametrize("seed", range(30))
def test_tree_forest_predicates_match_networkx(fn, directed, seed):
    for fg, ng in (_random_tree(seed, directed), _random_graph(seed, directed)):
        try:
            expected = getattr(nx, fn)(ng)
        except nx.NetworkXPointlessConcept:
            with pytest.raises(nx.NetworkXPointlessConcept):
                getattr(fnx, fn)(fg)
            continue
        assert getattr(fnx, fn)(fg) == expected


@pytest.mark.parametrize("fn", ["is_branching", "is_arborescence"])
@pytest.mark.parametrize("seed", range(40))
def test_directed_branching_predicates_match_networkx(fn, seed):
    for fg, ng in (_random_tree(seed, True), _random_graph(seed, True)):
        assert getattr(fnx, fn)(fg) == getattr(nx, fn)(ng)


def test_tree_predicate_goldens():
    assert fnx.is_tree(fnx.path_graph(4))
    assert not fnx.is_tree(fnx.cycle_graph(4))
    assert fnx.is_forest(fnx.Graph([(0, 1), (2, 3)]))  # two disjoint edges
    assert fnx.is_arborescence(fnx.DiGraph([(0, 1), (0, 2), (1, 3)]))
    # A node with two parents is not an arborescence.
    assert not fnx.is_arborescence(fnx.DiGraph([(0, 2), (1, 2)]))


@pytest.mark.parametrize("fn", ["is_tree", "is_forest"])
def test_empty_graph_raises_like_networkx(fn):
    with pytest.raises(nx.NetworkXPointlessConcept):
        getattr(fnx, fn)(fnx.Graph())
    with pytest.raises(nx.NetworkXPointlessConcept):
        getattr(nx, fn)(nx.Graph())
