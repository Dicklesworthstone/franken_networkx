"""Laplacian spectral moments tie the Laplacian spectrum to the degrees.

For L = D - A with eigenvalues mu_i:
  sum_i mu_i      = trace(L)   = sum of degrees = 2|E|;
  sum_i mu_i^2    = trace(L^2) = sum(d_i^2) + 2|E|;
  every mu_i >= 0 (L is positive semidefinite) and the smallest is 0.
This validates laplacian_spectrum from the eigenvalue side against the degree
sequence (the zero-eigenvalue multiplicity = #components is checked elsewhere,
5dkg5; this checks the moment/degree identities). Oracle-free, independent of
networkx.

No mocks: real fnx (numpy only to sum eigenvalue powers).
"""

from __future__ import annotations

import math
import random

import pytest
import franken_networkx as fnx

np = pytest.importorskip("numpy")


@pytest.mark.parametrize("seed", range(30))
def test_laplacian_moments_match_degrees(seed):
    r = random.Random(seed)
    n = r.randint(4, 9)
    edges = [(u, v) for u in range(n) for v in range(u + 1, n) if r.random() < 0.45]
    g = fnx.Graph(); g.add_nodes_from(range(n)); g.add_edges_from(edges)

    mu = fnx.laplacian_spectrum(g).real
    degs = np.array([d for _, d in g.degree()])
    m = g.number_of_edges()

    # First moment: trace(L) = sum of degrees = 2|E|.
    assert mu.sum() == pytest.approx(2 * m, abs=1e-5)
    assert mu.sum() == pytest.approx(degs.sum(), abs=1e-5)
    # Second moment: trace(L^2) = sum(d^2) + 2|E|.
    assert (mu ** 2).sum() == pytest.approx((degs ** 2).sum() + 2 * m, abs=1e-4)
    # Positive semidefinite, with a zero eigenvalue.
    assert mu.min() == pytest.approx(0.0, abs=1e-6)
    assert mu.min() > -1e-6


@pytest.mark.parametrize("n", [3, 4, 5, 6])
def test_complete_graph_laplacian_moments(n):
    # K_n Laplacian spectrum: 0 once, n with multiplicity n-1.
    mu = fnx.laplacian_spectrum(fnx.complete_graph(n)).real
    assert mu.sum() == pytest.approx(n * (n - 1), abs=1e-5)        # = 2|E|
    assert (mu ** 2).sum() == pytest.approx(n ** 2 * (n - 1), abs=1e-4)
    # Sanity: |E| recovered from the first moment.
    assert mu.sum() / 2 == pytest.approx(math.comb(n, 2), abs=1e-5)
