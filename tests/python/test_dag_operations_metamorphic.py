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


def _relabelled_dag(seed):
    """A DAG whose topological order is NOT its sorted-label order.

    _random_dag only emits u -> v with u < v, so 0..n-1 is always a valid
    topological order and the order check above cannot distinguish a real sort
    from one that returns the nodes untouched. Shuffling the labels breaks that.
    """
    r = random.Random(seed + 5000)
    n = r.randint(5, 10)
    g = fnx.DiGraph()
    g.add_nodes_from(range(n))
    for u in range(n):
        for v in range(u + 1, n):
            if r.random() < 0.4:
                g.add_edge(u, v)
    permutation = list(range(n))
    r.shuffle(permutation)
    return fnx.relabel_nodes(g, {i: permutation[i] for i in range(n)}), n


@pytest.mark.parametrize("seed", range(60))
def test_topological_order_on_a_relabelled_dag(seed):
    """The order check, on a family where the trivial answer is wrong."""
    g, n = _relabelled_dag(seed)

    order = list(fnx.topological_sort(g))
    assert sorted(order) == sorted(g.nodes())      # a permutation of the nodes
    position = {node: i for i, node in enumerate(order)}
    for u, v in g.edges():
        assert position[u] < position[v]


def test_relabelled_family_defeats_the_trivial_order():
    """Guards the test above: it is only stronger if sorted order is invalid."""
    defeated = 0
    for seed in range(60):
        g, _ = _relabelled_dag(seed)
        position = {node: i for i, node in enumerate(sorted(g.nodes()))}
        if any(position[u] >= position[v] for u, v in g.edges()):
            defeated += 1
    # Measured 60/60; assert a floor so the family cannot drift back to one
    # where returning the nodes in label order would pass.
    assert defeated >= 45, f"sorted order is still valid on {60 - defeated} draws"


@pytest.mark.parametrize(
    "call",
    [
        lambda lib, g: lib.transitive_reduction(g),
        lambda lib, g: list(lib.topological_sort(g)),
        lambda lib, g: list(lib.topological_generations(g)),
        lambda lib, g: lib.dag_longest_path_length(g),
    ],
    ids=["transitive_reduction", "topological_sort", "topological_generations", "longest_path"],
)
def test_cyclic_input_is_refused_like_networkx(call):
    """Every function here is DAG-only; none of the refusals was exercised."""
    cyclic = fnx.DiGraph([(0, 1), (1, 2), (2, 0)])
    ncyclic = nx.DiGraph([(0, 1), (1, 2), (2, 0)])

    def outcome(fn):
        try:
            fn()
            return ("returned", None)
        except Exception as exc:  # noqa: BLE001 - the type IS the assertion
            return ("raised", type(exc).__name__)

    got = outcome(lambda: call(fnx, cyclic))
    want = outcome(lambda: call(nx, ncyclic))
    assert want[0] == "raised", "networkx no longer refuses a cycle — retune the case"
    assert got == want
