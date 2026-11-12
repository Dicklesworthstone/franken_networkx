"""Oracle-free SCC / condensation invariants for directed graphs.

* the strongly connected components partition the node set
* each multi-node SCC is itself strongly connected
* the condensation is a DAG with one node per SCC
* ``number_strongly_connected_components`` == number of SCCs
* SCCs refine the weakly connected components; ``#SCC >= #WCC``
* every attracting component is an SCC

br-r37-c1-79m5b
"""

from __future__ import annotations

import random

import pytest
import franken_networkx as fnx


def _digraph(seed, p=0.32):
    rng = random.Random(seed)
    n = rng.randint(5, 11)
    g = fnx.DiGraph()
    g.add_nodes_from(range(n))
    for u in range(n):
        for v in range(n):
            if u != v and rng.random() < p:
                g.add_edge(u, v)
    return g, n


@pytest.mark.parametrize("seed", range(80))
def test_scc_partition_and_condensation(seed):
    g, n = _digraph(seed)
    sccs = list(fnx.strongly_connected_components(g))
    # Partition: disjoint and covering.
    seen = set()
    for c in sccs:
        assert seen.isdisjoint(c)
        seen |= c
    assert seen == set(range(n))
    # Each SCC is strongly connected.
    for c in sccs:
        if len(c) > 1:
            assert fnx.is_strongly_connected(g.subgraph(c))
    # Count helper agrees.
    assert fnx.number_strongly_connected_components(g) == len(sccs)
    # Condensation is a DAG with one node per SCC.
    cond = fnx.condensation(g)
    assert fnx.is_directed_acyclic_graph(cond)
    assert cond.number_of_nodes() == len(sccs)


@pytest.mark.parametrize("seed", range(60))
def test_scc_refines_wcc(seed):
    g, _ = _digraph(seed, p=0.28)
    sccs = list(fnx.strongly_connected_components(g))
    wccs = list(fnx.weakly_connected_components(g))
    for sc in sccs:
        assert any(sc <= wc for wc in wccs)
    assert fnx.number_strongly_connected_components(g) >= (
        fnx.number_weakly_connected_components(g)
    )


@pytest.mark.parametrize("seed", range(60))
def test_attracting_components_are_sccs(seed):
    g, _ = _digraph(seed)
    scc_sets = [set(c) for c in fnx.strongly_connected_components(g)]
    for ac in fnx.attracting_components(g):
        assert set(ac) in scc_sets
