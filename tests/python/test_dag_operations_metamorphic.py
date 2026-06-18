"""DAG operations: differential parity + structural invariants.

Transitive closure/reduction, topological order, and ancestor/descendant sets
obey structural laws (reduction ⊆ original ⊆ closure; every edge respects the
topological order; closure/reduction preserve reachability). Checking the laws
*and* nx parity catches bugs a single comparison would miss.

No mocks: real fnx and real networkx on randomly generated DAGs.
"""

from __future__ import annotations

import random

import pytest
import networkx as nx
import franken_networkx as fnx


def _random_dag(seed):
    r = random.Random(seed)
    n = r.randint(5, 10)
    g = fnx.DiGraph()
    g.add_nodes_from(range(n))
    for u in range(n):
        for v in range(u + 1, n):  # only forward edges → acyclic
            if r.random() < 0.4:
                g.add_edge(u, v)
    ng = nx.DiGraph(list(g.edges()))
    ng.add_nodes_from(range(n))
    return g, ng, n


@pytest.mark.parametrize("seed", range(60))
def test_transitive_reduction_and_closure(seed):
    g, ng, n = _random_dag(seed)

    tr = fnx.transitive_reduction(g)
    ntr = nx.transitive_reduction(ng)
    assert set(tr.edges()) == set(ntr.edges())
    # Reduction is a subgraph of the original.
    assert set(tr.edges()).issubset(set(g.edges()))

    tc = fnx.transitive_closure(g)
    ntc = nx.transitive_closure(ng)
    assert set(tc.edges()) == set(ntc.edges())
    # Closure is a supergraph of the original.
    assert set(g.edges()).issubset(set(tc.edges()))

    # Reduction preserves reachability: closure(reduction) == closure(original).
    tr_as_nx = nx.DiGraph(list(tr.edges()))
    tr_as_nx.add_nodes_from(range(n))
    assert set(nx.transitive_closure(tr_as_nx).edges()) == set(ntc.edges())


@pytest.mark.parametrize("seed", range(60))
def test_topological_order_and_reachability(seed):
    g, ng, n = _random_dag(seed)

    # topological_sort produces a valid linear extension.
    order = list(fnx.topological_sort(g))
    pos = {x: i for i, x in enumerate(order)}
    assert len(order) == n
    for u, v in g.edges():
        assert pos[u] < pos[v]

    # topological_generations matches nx (layer by layer).
    fg = [sorted(layer) for layer in fnx.topological_generations(g)]
    nng = [sorted(layer) for layer in nx.topological_generations(ng)]
    assert fg == nng

    # ancestors / descendants match nx for every node.
    for node in range(n):
        assert fnx.ancestors(g, node) == nx.ancestors(ng, node)
        assert fnx.descendants(g, node) == nx.descendants(ng, node)

    # longest path length matches.
    assert fnx.dag_longest_path_length(g) == nx.dag_longest_path_length(ng)


def test_descendants_are_reachable_ancestors_symmetric():
    # v ∈ descendants(u)  ⟺  u ∈ ancestors(v).
    g, ng, n = _random_dag(7)
    for u in range(n):
        for v in fnx.descendants(g, u):
            assert u in fnx.ancestors(g, v)
