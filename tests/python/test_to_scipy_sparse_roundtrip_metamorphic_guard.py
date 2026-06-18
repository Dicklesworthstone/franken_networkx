"""Metamorphic round-trip guard for to_scipy_sparse_array / from_scipy_sparse_array.

to_scipy_sparse_array was optimized (native COO + dtype handling). This locks its
correctness by self-consistency: from_scipy_sparse_array(to_scipy_sparse_array(G,
nodelist=sorted), ...) recovers G's adjacency + weights by index, for the simple
graph types (scipy sparse sums parallel weights, so multigraphs are out of scope).

Relations:
  * matrix shape == (n, n), nnz matches the directed/undirected edge count;
  * A[i, j] == weight of edge (nodelist[i], nodelist[j]) (or 0);
  * round-trip: from_scipy_sparse_array(A) has edge (i, j, weight=A[i,j]) iff G has
    edge (nodelist[i], nodelist[j]) with that weight.

No mocks, NO networkx — pure fnx self-consistency (scipy/numpy for the matrix).
"""

from __future__ import annotations

import random

import pytest
import franken_networkx as fnx

pytest.importorskip("scipy")
np = pytest.importorskip("numpy")

_TYPES = [fnx.Graph, fnx.DiGraph]


def _build(cls, seed):
    r = random.Random(seed)
    n = r.randint(4, 9)
    g = cls()
    g.add_nodes_from(range(n))
    for u in range(n):
        for v in range(n):
            if u != v and (g.is_directed() or u < v) and r.random() < 0.45:
                g.add_edge(u, v, weight=r.randint(1, 9))
    return g, n


@pytest.mark.parametrize("cls", _TYPES)
@pytest.mark.parametrize("seed", range(20))
def test_to_scipy_roundtrip(cls, seed):
    g, n = _build(cls, seed)
    nodelist = sorted(g.nodes())
    idx = {node: i for i, node in enumerate(nodelist)}
    A = fnx.to_scipy_sparse_array(g, nodelist=nodelist, weight="weight")
    assert A.shape == (n, n)

    dense = A.toarray()
    for u, v, d in g.edges(data=True):
        assert dense[idx[u], idx[v]] == d["weight"]

    # Round-trip recovers adjacency + weights by index.
    h = fnx.from_scipy_sparse_array(A, create_using=cls())
    assert h.number_of_edges() == g.number_of_edges()
    for i in range(n):
        for j in range(n):
            g_has = g.has_edge(nodelist[i], nodelist[j])
            assert h.has_edge(i, j) == g_has
            if g_has:
                assert h[i][j]["weight"] == g[nodelist[i]][nodelist[j]]["weight"]
