"""Differential parity for ``triads_by_type`` and ``is_triad``.

``triads_by_type(G)`` groups every node-triple of a digraph by its triad
census type (e.g. ``"003"``, ``"030T"``); ``is_triad(G)`` is True iff
``G`` is a 3-node digraph. Neither had a dedicated test file.

``triads_by_type`` returns lists of subgraph objects in an
implementation-defined order, so this compares the grouping by
*node-set* per census type (order-invariant, the meaningful invariant).

br-r37-c1-he53g
"""

from __future__ import annotations

import random

import pytest
import networkx as nx
import franken_networkx as fnx
from franken_networkx.algorithms.triads import (
    triads_by_type as fnx_triads_by_type,
    is_triad as fnx_is_triad,
)
from networkx.algorithms.triads import (
    triads_by_type as nx_triads_by_type,
    is_triad as nx_is_triad,
)


def _grouped_node_sets(by_type):
    return {
        census: {frozenset(g.nodes()) for g in triads}
        for census, triads in by_type.items()
    }


def _digraph_pair(seed, p=0.35):
    rng = random.Random(seed)
    n = rng.randint(3, 7)
    fg = fnx.DiGraph()
    ng = nx.DiGraph()
    fg.add_nodes_from(range(n))
    ng.add_nodes_from(range(n))
    for u in range(n):
        for v in range(n):
            if u != v and rng.random() < p:
                fg.add_edge(u, v)
                ng.add_edge(u, v)
    return fg, ng


@pytest.mark.parametrize("seed", range(50))
def test_triads_by_type_matches_networkx(seed):
    fg, ng = _digraph_pair(seed)
    assert _grouped_node_sets(fnx_triads_by_type(fg)) == _grouped_node_sets(
        nx_triads_by_type(ng)
    )


@pytest.mark.parametrize("seed", range(30))
def test_is_triad_matches_networkx(seed):
    rng = random.Random(seed)
    n = rng.randint(2, 5)
    edges = [
        (u, v)
        for u in range(n)
        for v in range(n)
        if u != v and rng.random() < 0.4
    ]
    fg = fnx.DiGraph()
    ng = nx.DiGraph()
    fg.add_nodes_from(range(n))
    ng.add_nodes_from(range(n))
    fg.add_edges_from(edges)
    ng.add_edges_from(edges)
    assert fnx_is_triad(fg) == nx_is_triad(ng)


def test_is_triad_goldens():
    assert fnx_is_triad(fnx.DiGraph([(0, 1), (1, 2)]))           # 3 nodes
    assert not fnx_is_triad(fnx.DiGraph([(0, 1)]))               # 2 nodes
    g4 = fnx.DiGraph()
    g4.add_nodes_from(range(4))
    assert not fnx_is_triad(g4)                                  # 4 nodes


def test_triads_by_type_census_total_is_all_triples():
    # Every unordered node-triple lands in exactly one census bucket.
    import itertools

    g = fnx.DiGraph([(0, 1), (1, 2), (2, 0), (2, 3), (3, 4)])
    g.add_nodes_from(range(5))
    by_type = fnx_triads_by_type(g)
    total = sum(len(v) for v in by_type.values())
    assert total == len(list(itertools.combinations(range(5), 3)))
