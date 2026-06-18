"""Laplacian spectral invariants (spectral graph theory cross-checks).

The Laplacian and its spectrum obey strong identities that cross-check
laplacian_matrix, adjacency_matrix, laplacian_spectrum, and
number_connected_components:
  - L = D - A (degree diagonal minus adjacency);
  - row sums are zero; trace(L) = sum of degrees = 2|E|;
  - the smallest Laplacian eigenvalue is 0;
  - the multiplicity of eigenvalue 0 equals the number of connected components;
  - the eigenvalues sum to 2|E|;
  - the graph is connected iff the second-smallest eigenvalue (lambda_2) > 0.
All are oracle-free (theorems, not a reference implementation).

No mocks: real fnx (numpy for the eigen-decomposition).
"""

from __future__ import annotations

import random

import numpy as np
import pytest
import franken_networkx as fnx


def _graph(seed):
    r = random.Random(seed)
    n = r.randint(5, 10)
    edges = [(u, v) for u in range(n) for v in range(u + 1, n) if r.random() < 0.35]
    g = fnx.Graph(); g.add_nodes_from(range(n)); g.add_edges_from(edges)
    return g, n


@pytest.mark.parametrize("seed", range(40))
def test_laplacian_structure(seed):
    g, n = _graph(seed)
    L = fnx.laplacian_matrix(g).toarray().astype(float)
    A = fnx.adjacency_matrix(g).toarray().astype(float)
    D = np.diag(A.sum(axis=1))
    assert np.allclose(L, D - A)               # L = D - A
    assert np.allclose(L.sum(axis=1), 0)       # row sums zero
    assert abs(np.trace(L) - 2 * g.number_of_edges()) < 1e-9   # trace = 2|E|


@pytest.mark.parametrize("seed", range(40))
def test_laplacian_spectrum_invariants(seed):
    g, n = _graph(seed)
    evals = sorted(np.real(fnx.laplacian_spectrum(g)))

    assert abs(evals[0]) < 1e-8                 # smallest eigenvalue is 0
    assert abs(sum(evals) - 2 * g.number_of_edges()) < 1e-6   # eigsum = 2|E|

    # Multiplicity of eigenvalue 0 == number of connected components.
    mult0 = sum(1 for e in evals if abs(e) < 1e-8)
    assert mult0 == fnx.number_connected_components(g)

    # Connected graph (n>1) has a strictly positive Fiedler value.
    if fnx.is_connected(g) and n > 1:
        assert evals[1] > 1e-8


def test_complete_graph_laplacian_spectrum_closed_form():
    # K_n Laplacian spectrum: 0 once, n with multiplicity n-1.
    for n in (4, 5, 6):
        evals = sorted(round(e, 6) for e in np.real(fnx.laplacian_spectrum(fnx.complete_graph(n))))
        assert evals[0] == 0
        assert all(abs(e - n) < 1e-6 for e in evals[1:])
