"""Metamorphic (oracle-free) round-trip guard for to_numpy_array.

to_numpy_array was optimized to a native COO path (11x->2x); this locks its
correctness by self-consistent metamorphic relations rather than a reference:

  * undirected graph -> symmetric matrix (A == A.T);
  * no self-loops -> zero diagonal;
  * A[i, j] == the weight of edge (nodelist[i], nodelist[j]), else 0;
  * #nonzero upper-triangle entries == G.number_of_edges();
  * ROUND-TRIP: from_numpy_array(A) has edge (i, j) with weight A[i, j] iff G has
    edge (nodelist[i], nodelist[j]) with that weight.

These hold regardless of networkx, so they catch a COO bug fnx+nx could share.

No mocks, NO networkx parity — pure fnx self-consistency (numpy for the matrix).
"""

from __future__ import annotations

import random

import pytest
import franken_networkx as fnx

np = pytest.importorskip("numpy")


def _weighted_graph(seed):
    r = random.Random(seed)
    n = r.randint(5, 10)
    g = fnx.Graph()
    g.add_nodes_from(range(n))
    for u in range(n):
        for v in range(u + 1, n):
            if r.random() < 0.45:
                g.add_edge(u, v, weight=r.randint(1, 9))
    return g, n


@pytest.mark.parametrize("seed", range(20))
def test_to_numpy_array_metamorphic_and_roundtrip(seed):
    g, n = _weighted_graph(seed)
    nodelist = sorted(g.nodes())
    idx = {node: i for i, node in enumerate(nodelist)}
    A = fnx.to_numpy_array(g, nodelist=nodelist, weight="weight")

    # Symmetric (undirected) + zero diagonal (no self-loops).
    assert np.array_equal(A, A.T)
    assert np.array_equal(np.diag(A), np.zeros(n))
    # Entry == edge weight, else 0.
    for u, v, d in g.edges(data=True):
        assert A[idx[u], idx[v]] == d["weight"]
    # #nonzero upper triangle == edge count.
    assert int(np.count_nonzero(np.triu(A, 1))) == g.number_of_edges()

    # ROUND-TRIP: from_numpy_array recovers the same adjacency (by index) + weights.
    h = fnx.from_numpy_array(A)
    assert h.number_of_edges() == g.number_of_edges()
    for i in range(n):
        for j in range(i + 1, n):
            g_has = g.has_edge(nodelist[i], nodelist[j])
            assert h.has_edge(i, j) == g_has
            if g_has:
                assert h[i][j]["weight"] == g[nodelist[i]][nodelist[j]]["weight"]
