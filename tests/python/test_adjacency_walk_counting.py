"""Adjacency-matrix walk-counting identities (algebra <-> combinatorics).

Powers of the adjacency matrix count walks: (A^k)[i][j] is the number of length-k
walks from i to j. This yields identities cross-checking adjacency_matrix,
triangles, degree, and number_of_edges:
  - sum(A) = 2|E|; A is symmetric (undirected);
  - trace(A^2) = sum of degrees = 2|E|;
  - A^2[i][i] = degree(i) (2-walks returning to i);
  - trace(A^3) = 6 * (number of triangles);
  - A^3[i][i] / 2 = number of triangles through node i.
All are oracle-free (combinatorial theorems), independent of networkx.

No mocks: real fnx (numpy for the matrix powers).
"""

from __future__ import annotations

import random

import numpy as np
import pytest
import franken_networkx as fnx


def _graph(seed):
    r = random.Random(seed)
    n = r.randint(5, 10)
    edges = [(u, v) for u in range(n) for v in range(u + 1, n) if r.random() < 0.4]
    g = fnx.Graph(); g.add_nodes_from(range(n)); g.add_edges_from(edges)
    return g, n


@pytest.mark.parametrize("seed", range(40))
def test_a_squared_identities(seed):
    g, n = _graph(seed)
    A = fnx.adjacency_matrix(g).toarray().astype(float)
    assert np.allclose(A, A.T)                                   # symmetric
    assert abs(A.sum() - 2 * g.number_of_edges()) < 1e-9        # sum(A) = 2|E|
    A2 = A @ A
    assert abs(np.trace(A2) - 2 * g.number_of_edges()) < 1e-9   # trace(A^2) = 2|E|
    degs = dict(g.degree())
    for i in range(n):
        assert abs(A2[i][i] - degs[i]) < 1e-9                    # A^2 diag = degree


@pytest.mark.parametrize("seed", range(40))
def test_a_cubed_counts_triangles(seed):
    g, n = _graph(seed)
    A = fnx.adjacency_matrix(g).toarray().astype(float)
    A3 = A @ A @ A
    num_triangles = sum(fnx.triangles(g).values()) // 3
    # trace(A^3) = 6 * number of triangles.
    assert abs(np.trace(A3) - 6 * num_triangles) < 1e-6
    # Per-node: A^3[i][i] / 2 = triangles through node i.
    tri = fnx.triangles(g)
    for i in range(n):
        assert abs(A3[i][i] / 2 - tri[i]) < 1e-6


def test_complete_graph_triangle_count_via_trace():
    # K_n has C(n,3) triangles; trace(A^3) must be 6 * C(n,3).
    import math
    for n in (4, 5, 6):
        A = fnx.adjacency_matrix(fnx.complete_graph(n)).toarray().astype(float)
        assert abs(np.trace(A @ A @ A) - 6 * math.comb(n, 3)) < 1e-6
