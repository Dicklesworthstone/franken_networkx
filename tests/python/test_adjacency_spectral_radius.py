"""Adjacency spectral radius closed forms + degree bounds.

The spectral radius (largest-magnitude adjacency eigenvalue) has exact closed
forms for named graphs and a universal degree bound, cross-checking
adjacency_spectrum against the degree sequence:
  - complete K_n:            rho = n - 1;
  - cycle C_n:               rho = 2  (2-regular);
  - complete bipartite K_mn: rho = sqrt(m*n);
  - d-regular graph:         rho = d  (Perron-Frobenius);
  - any graph:               avg_degree <= rho <= max_degree.
Oracle-free, independent of networkx.

No mocks: real fnx (numpy for the spectrum).
"""

from __future__ import annotations

import math
import random

import numpy as np
import pytest
import franken_networkx as fnx


def _spectral_radius(g):
    return max(abs(e) for e in np.real(fnx.adjacency_spectrum(g)))


@pytest.mark.parametrize("n", [4, 5, 6, 7])
def test_complete_and_cycle_spectral_radius(n):
    assert _spectral_radius(fnx.complete_graph(n)) == pytest.approx(n - 1, abs=1e-4)
    assert _spectral_radius(fnx.cycle_graph(n)) == pytest.approx(2, abs=1e-4)


@pytest.mark.parametrize("m,n", [(2, 3), (3, 3), (2, 4), (3, 5)])
def test_complete_bipartite_spectral_radius(m, n):
    assert _spectral_radius(
        fnx.complete_bipartite_graph(m, n)
    ) == pytest.approx(math.sqrt(m * n), abs=1e-4)


def test_regular_graph_spectral_radius_is_degree():
    # The Petersen graph is 3-regular -> spectral radius 3.
    assert _spectral_radius(fnx.petersen_graph()) == pytest.approx(3, abs=1e-4)
    # A d-regular graph has spectral radius exactly d.
    for n, d in [(6, 3), (8, 4)]:
        if (n * d) % 2 == 0:
            g = fnx.random_regular_graph(d, n, seed=n)
            assert _spectral_radius(g) == pytest.approx(d, abs=1e-4)


@pytest.mark.parametrize("seed", range(20))
def test_spectral_radius_between_avg_and_max_degree(seed):
    r = random.Random(seed)
    n = r.randint(5, 9)
    edges = [(u, v) for u in range(n) for v in range(u + 1, n) if r.random() < 0.4]
    g = fnx.Graph(); g.add_nodes_from(range(n)); g.add_edges_from(edges)
    if g.number_of_edges() == 0:
        pytest.skip("no edges")
    degs = [d for _, d in g.degree()]
    rho = _spectral_radius(g)
    # avg_degree <= spectral_radius <= max_degree.
    assert sum(degs) / n - 1e-6 <= rho <= max(degs) + 1e-6
