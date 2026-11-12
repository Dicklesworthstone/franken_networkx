"""Differential + golden parity for ``antichains`` / ``all_topological_sorts``.

``antichains(G)`` enumerates every antichain (set of pairwise-incomparable
nodes) of a DAG; ``all_topological_sorts(G)`` enumerates every valid
topological ordering. Neither had a dedicated test file. Both enumerate in
an implementation-defined order, so this compares the order-invariant set
of results.

br-r37-c1-fzpg2
"""

from __future__ import annotations

import random

import pytest
import networkx as nx
import franken_networkx as fnx


def _random_dag(seed, p=0.35):
    rng = random.Random(seed)
    n = rng.randint(3, 6)
    fg = fnx.DiGraph()
    ng = nx.DiGraph()
    fg.add_nodes_from(range(n))
    ng.add_nodes_from(range(n))
    for u in range(n):
        for v in range(u + 1, n):
            if rng.random() < p:
                fg.add_edge(u, v)
                ng.add_edge(u, v)
    return fg, ng


def _antichain_set(it):
    return sorted(tuple(sorted(a)) for a in it)


def _ordering_set(it):
    return sorted(tuple(t) for t in it)


@pytest.mark.parametrize("seed", range(50))
def test_antichains_match_networkx(seed):
    fg, ng = _random_dag(seed)
    assert _antichain_set(fnx.antichains(fg)) == _antichain_set(nx.antichains(ng))


@pytest.mark.parametrize("seed", range(50))
def test_all_topological_sorts_match_networkx(seed):
    fg, ng = _random_dag(seed)
    assert _ordering_set(fnx.all_topological_sorts(fg)) == _ordering_set(
        nx.all_topological_sorts(ng)
    )


def test_goldens():
    # A chain has only singleton (and empty) antichains and one ordering.
    chain = fnx.DiGraph([(0, 1), (1, 2)])
    assert _antichain_set(fnx.antichains(chain)) == [(), (0,), (1,), (2,)]
    assert list(fnx.all_topological_sorts(chain)) == [[0, 1, 2]]
    # A fork (0->2, 1->2): {0, 1} is an antichain; two valid orderings.
    fork = fnx.DiGraph([(0, 2), (1, 2)])
    assert (0, 1) in _antichain_set(fnx.antichains(fork))
    assert _ordering_set(fnx.all_topological_sorts(fork)) == [(0, 1, 2), (1, 0, 2)]


@pytest.mark.parametrize("fn", ["antichains", "all_topological_sorts"])
def test_cyclic_input_raises_like_networkx(fn):
    # Both raise NetworkXUnfeasible (a NetworkXException sibling of
    # NetworkXError, not a subclass) — fnx matches nx on the exact type.
    fg = fnx.DiGraph([(0, 1), (1, 2), (2, 0)])
    ng = nx.DiGraph([(0, 1), (1, 2), (2, 0)])
    with pytest.raises(nx.NetworkXUnfeasible) as fnx_exc:
        list(getattr(fnx, fn)(fg))
    with pytest.raises(nx.NetworkXUnfeasible) as nx_exc:
        list(getattr(nx, fn)(ng))
    assert type(fnx_exc.value) is type(nx_exc.value)
