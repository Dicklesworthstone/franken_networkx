"""Spectral / matrix parity with networkx.

Laplacian, normalized-Laplacian, adjacency and incidence matrices must match
networkx exactly, and the spectra / algebraic connectivity (order-invariant
scalars) must agree numerically.

NOTE: both libraries build their matrices in node-iteration order, so the
graphs MUST be constructed with identical node order — ``add_nodes_from(
range(n))`` before the edges in BOTH. Building one side as
``nx.Graph(edge_list)`` would introduce nodes in edge order, permuting its
matrix and producing a false mismatch (the eigenvalues would still agree —
that permutation-similarity is the tell). This test avoids that artifact.

No mocks: real fnx and real networkx on identically-constructed graphs.
"""

from __future__ import annotations

import random

import numpy as np
import pytest
import networkx as nx
import franken_networkx as fnx


def _identical_pair(seed):
    r = random.Random(seed)
    n = r.randint(5, 10)
    edges = [(u, v) for u in range(n) for v in range(u + 1, n) if r.random() < 0.5]
    fg = fnx.Graph(); fg.add_nodes_from(range(n)); fg.add_edges_from(edges)
    ng = nx.Graph(); ng.add_nodes_from(range(n)); ng.add_edges_from(edges)
    return fg, ng, n


@pytest.mark.parametrize("seed", range(30))
def test_matrices_match_networkx(seed):
    fg, ng, n = _identical_pair(seed)
    assert np.allclose(fnx.adjacency_matrix(fg).toarray(), nx.adjacency_matrix(ng).toarray())
    assert np.allclose(fnx.laplacian_matrix(fg).toarray(), nx.laplacian_matrix(ng).toarray())
    assert np.allclose(
        fnx.incidence_matrix(fg).toarray(), nx.incidence_matrix(ng).toarray()
    )
    if fnx.is_connected(fg):
        assert np.allclose(
            fnx.normalized_laplacian_matrix(fg).toarray(),
            nx.normalized_laplacian_matrix(ng).toarray(),
        )


@pytest.mark.parametrize("seed", range(30))
def test_spectra_and_algebraic_connectivity(seed):
    fg, ng, n = _identical_pair(seed)
    assert np.allclose(
        sorted(np.real(fnx.laplacian_spectrum(fg))),
        sorted(np.real(nx.laplacian_spectrum(ng))),
        atol=1e-6,
    )
    assert np.allclose(
        sorted(np.real(fnx.adjacency_spectrum(fg))),
        sorted(np.real(nx.adjacency_spectrum(ng))),
        atol=1e-6,
    )
    if fnx.is_connected(fg):
        assert abs(
            fnx.algebraic_connectivity(fg) - nx.algebraic_connectivity(ng)
        ) < 1e-6
