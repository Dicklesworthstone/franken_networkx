"""Directed-graph reverse: involution + degree-swap invariants.

Reversing a digraph flips every arc. Its defining properties cross-check
reverse against the degree views and the SCC decomposition:
  - reverse swaps each arc (u, v) -> (v, u);
  - reverse is an involution: reverse(reverse(G)) == G;
  - reverse swaps in-degree and out-degree (in_degree of reverse == out_degree of G);
  - node and edge counts are unchanged;
  - the strongly connected components are preserved (reachability is symmetric
    under arc reversal).
Oracle-free, independent of networkx.

No mocks: real fnx.
"""

from __future__ import annotations

import random

import pytest
import franken_networkx as fnx


def _digraph(seed):
    r = random.Random(seed)
    n = r.randint(4, 9)
    edges = [(u, v) for u in range(n) for v in range(n) if u != v and r.random() < 0.35]
    g = fnx.DiGraph(edges)
    g.add_nodes_from(range(n))
    return g


def _edges(g):
    return sorted((u, v) for u, v in g.edges())


@pytest.mark.parametrize("seed", range(40))
def test_reverse_swaps_arcs_and_is_involution(seed):
    g = _digraph(seed)
    rev = fnx.reverse(g)
    # Each arc is flipped.
    assert _edges(rev) == sorted((v, u) for u, v in g.edges())
    # Reversing twice recovers the original.
    assert _edges(fnx.reverse(rev)) == _edges(g)
    # Counts unchanged.
    assert rev.number_of_nodes() == g.number_of_nodes()
    assert rev.number_of_edges() == g.number_of_edges()


@pytest.mark.parametrize("seed", range(40))
def test_reverse_swaps_degrees_and_preserves_sccs(seed):
    g = _digraph(seed)
    rev = fnx.reverse(g)
    # in-degree of the reverse equals out-degree of the original (and vice-versa).
    assert dict(rev.in_degree()) == dict(g.out_degree())
    assert dict(rev.out_degree()) == dict(g.in_degree())
    # Strongly connected components are invariant under reversal.
    scc_g = sorted(sorted(c) for c in fnx.strongly_connected_components(g))
    scc_r = sorted(sorted(c) for c in fnx.strongly_connected_components(rev))
    assert scc_g == scc_r
