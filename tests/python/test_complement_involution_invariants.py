"""Graph complement: involution + degree relationship invariants.

The complement swaps present and absent edges (within K_n). Its defining
properties cross-check complement against the degree sequence and edge count:
  - involution: complement(complement(G)) == G;
  - degree: deg_complement(v) = (n-1) - deg_G(v);
  - edge count: |E(G)| + |E(complement(G))| = C(n, 2);
  - the node set is unchanged;
  - complement(K_n) is empty; complement(empty) is K_n.
These differ from the set-algebra (cluiw) and clique-duality (z0f6q) views.
Oracle-free, independent of networkx.

No mocks: real fnx.
"""

from __future__ import annotations

import math
import random

import pytest
import franken_networkx as fnx


def _edges(g):
    return sorted(tuple(sorted((u, v))) for u, v in g.edges())


@pytest.mark.parametrize("seed", range(40))
def test_complement_involution_and_degree(seed):
    r = random.Random(seed)
    n = r.randint(4, 9)
    edges = [(u, v) for u in range(n) for v in range(u + 1, n) if r.random() < 0.45]
    g = fnx.Graph(); g.add_nodes_from(range(n)); g.add_edges_from(edges)
    comp = fnx.complement(g)

    # Involution: complementing twice recovers the original.
    assert _edges(fnx.complement(comp)) == _edges(g)
    assert set(comp.nodes()) == set(g.nodes())
    # Degree relationship in the complement.
    dg = dict(g.degree())
    dc = dict(comp.degree())
    for v in g:
        assert dc[v] == (n - 1) - dg[v]
    # Edge counts partition K_n.
    assert g.number_of_edges() + comp.number_of_edges() == math.comb(n, 2)


@pytest.mark.parametrize("n", [3, 4, 5, 6])
def test_complement_of_complete_and_empty(n):
    # complement(K_n) has no edges.
    assert fnx.complement(fnx.complete_graph(n)).number_of_edges() == 0
    # complement(empty graph) is the complete graph.
    e = fnx.empty_graph(n)
    assert fnx.complement(e).number_of_edges() == math.comb(n, 2)
