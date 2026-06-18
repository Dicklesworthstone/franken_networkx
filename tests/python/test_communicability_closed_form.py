"""Communicability closed form (matrix exponential of the adjacency matrix).

Communicability between u and v is the (u,v) entry of exp(A):
  communicability(G)[u][v] = (exp(A))[u][v] = sum_k (A^k)[u][v] / k!  (walk sum).
This cross-checks communicability against the matrix exponential and ties it to
subgraph_centrality (existing tests cover nx parity, not these identities):
  - communicability[u][v] == expm(A)[u][v];
  - the matrix is symmetric (undirected graph);
  - the diagonal equals subgraph_centrality: communicability[u][u] == sc[u].
Oracle-free, independent of networkx.

No mocks: real fnx (scipy for the matrix exponential ground truth).
"""

from __future__ import annotations

import random

import pytest
import franken_networkx as fnx

np = pytest.importorskip("numpy")
expm = pytest.importorskip("scipy.linalg").expm


def _graph(seed):
    r = random.Random(seed)
    n = r.randint(4, 7)
    edges = [(u, v) for u in range(n) for v in range(u + 1, n) if r.random() < 0.5]
    g = fnx.Graph(); g.add_nodes_from(range(n)); g.add_edges_from(edges)
    return g, n


@pytest.mark.parametrize("seed", range(20))
def test_communicability_equals_matrix_exponential(seed):
    g, n = _graph(seed)
    if g.number_of_edges() == 0:
        pytest.skip("no edges")
    A = fnx.adjacency_matrix(g).toarray().astype(float)
    E = expm(A)
    comm = fnx.communicability(g)
    for u in range(n):
        for v in range(n):
            assert comm[u][v] == pytest.approx(E[u][v], abs=1e-6)
            # Symmetry for an undirected graph.
            assert comm[u][v] == pytest.approx(comm[v][u], abs=1e-9)


@pytest.mark.parametrize("seed", range(20))
def test_communicability_diagonal_is_subgraph_centrality(seed):
    g, n = _graph(seed)
    if g.number_of_edges() == 0:
        pytest.skip("no edges")
    comm = fnx.communicability(g)
    sc = fnx.subgraph_centrality(g)
    for u in range(n):
        assert comm[u][u] == pytest.approx(sc[u], abs=1e-5)
