"""Adjacency spectral moments tie the spectrum to graph counts.

The k-th moment of the adjacency spectrum is the trace of A^k, which counts
closed walks of length k:
  sum_i lambda_i      = trace(A)   = 0           (no self-loops);
  sum_i lambda_i^2    = trace(A^2) = 2|E|         (each edge -> 2 closed 2-walks);
  sum_i lambda_i^3    = trace(A^3) = 6 * #triangles.
This validates adjacency_spectrum from the eigenvalue side against |E| and the
triangle count (the matrix-walk test imp6j checks trace(A^k) via A directly; this
checks it via the eigenvalues). Oracle-free, independent of networkx.

No mocks: real fnx (numpy only to sum eigenvalue powers).
"""

from __future__ import annotations

import random

import pytest
import franken_networkx as fnx

np = pytest.importorskip("numpy")


@pytest.mark.parametrize("seed", range(30))
def test_spectral_moments_match_counts(seed):
    r = random.Random(seed)
    n = r.randint(4, 9)
    edges = [(u, v) for u in range(n) for v in range(u + 1, n) if r.random() < 0.45]
    g = fnx.Graph(); g.add_nodes_from(range(n)); g.add_edges_from(edges)

    ev = fnx.adjacency_spectrum(g).real
    # First moment: trace(A) = 0 for a simple graph (no self-loops).
    assert ev.sum() == pytest.approx(0.0, abs=1e-6)
    # Second moment: trace(A^2) = 2|E|.
    assert (ev ** 2).sum() == pytest.approx(2 * g.number_of_edges(), abs=1e-5)
    # Third moment: trace(A^3) = 6 * number of triangles.
    triangles = sum(fnx.triangles(g).values()) // 3
    assert (ev ** 3).sum() == pytest.approx(6 * triangles, abs=1e-4)


@pytest.mark.parametrize("n", [3, 4, 5])
def test_complete_graph_spectral_moments(n):
    ev = fnx.adjacency_spectrum(fnx.complete_graph(n)).real
    assert ev.sum() == pytest.approx(0.0, abs=1e-6)
    # K_n has C(n,2) edges and C(n,3) triangles.
    import math
    assert (ev ** 2).sum() == pytest.approx(2 * math.comb(n, 2), abs=1e-5)
    assert (ev ** 3).sum() == pytest.approx(6 * math.comb(n, 3), abs=1e-4)
