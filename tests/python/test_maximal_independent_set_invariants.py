"""maximal_independent_set invariants (independent + maximal + dominating).

maximal_independent_set is randomized (it depends on seed-driven choices and
does not match networkx value-for-value), so it is validated by its defining
PROPERTIES rather than by parity:
  - independence: no two chosen nodes are adjacent;
  - maximality: every non-chosen node is adjacent to a chosen one (otherwise it
    could be added);
  - a maximal independent set is necessarily a DOMINATING set;
  - any nodes passed as the required seed set are included.
These oracle-free invariants hold for whatever valid MIS is returned.

No mocks: real fnx.
"""

from __future__ import annotations

import random

import pytest
import franken_networkx as fnx


def _graph(seed):
    r = random.Random(seed)
    n = r.randint(5, 11)
    edges = [(u, v) for u in range(n) for v in range(u + 1, n) if r.random() < 0.35]
    g = fnx.Graph(); g.add_nodes_from(range(n)); g.add_edges_from(edges)
    return g, n


@pytest.mark.parametrize("seed", range(40))
def test_mis_is_independent_and_maximal(seed):
    g, n = _graph(seed)
    adj = {node: set(g.neighbors(node)) for node in g}
    mis = set(fnx.maximal_independent_set(g, seed=seed))

    # Independence: no edge inside the set.
    for u in mis:
        assert not (adj[u] & mis - {u})
    # Maximality: every node outside has a neighbor inside.
    for node in g:
        if node not in mis:
            assert adj[node] & mis


@pytest.mark.parametrize("seed", range(40))
def test_mis_is_a_dominating_set(seed):
    g, n = _graph(seed)
    mis = set(fnx.maximal_independent_set(g, seed=seed))
    # A maximal independent set is always a dominating set.
    assert fnx.is_dominating_set(g, mis)


@pytest.mark.parametrize("seed", range(20))
def test_required_seed_nodes_are_included(seed):
    g, n = _graph(seed)
    first = list(g.nodes())[0]
    mis = set(fnx.maximal_independent_set(g, nodes=[first], seed=seed))
    assert first in mis
    # Still independent and dominating with the forced seed.
    assert fnx.is_dominating_set(g, mis)
