"""Katz centrality closed form (resolvent of the adjacency matrix).

Katz centrality solves the linear system
  x = (I - alpha * A)^{-1} * beta * 1,
then normalises. For alpha below 1/lambda_max this is well defined. This
cross-checks katz_centrality_numpy against the resolvent directly (existing
tests cover nx conformance / the centrality matrix, not the linear-algebra
definition):
  - random graphs: katz vector is parallel to (I - alpha A)^{-1} beta;
  - the Katz scores satisfy the fixed point x = alpha A x + beta (up to the
    normalisation scale).
Oracle-free, independent of networkx.

No mocks: real fnx (numpy for the linear algebra).
"""

from __future__ import annotations

import random

import numpy as np
import pytest
import franken_networkx as fnx


@pytest.mark.parametrize("seed", range(20))
def test_katz_matches_resolvent(seed):
    r = random.Random(seed)
    n = r.randint(4, 7)
    edges = [(u, v) for u in range(n) for v in range(u + 1, n) if r.random() < 0.5]
    g = fnx.Graph(); g.add_nodes_from(range(n)); g.add_edges_from(edges)
    if g.number_of_edges() == 0:
        pytest.skip("no edges")

    A = fnx.adjacency_matrix(g).toarray().astype(float)
    alpha, beta = 0.1, 1.0
    raw = np.linalg.solve(np.eye(n) - alpha * A, beta * np.ones(n))
    raw = raw / np.linalg.norm(raw)

    kc = fnx.katz_centrality_numpy(g, alpha=alpha, beta=beta)
    vec = np.array([kc[i] for i in range(n)])
    # Katz scores are normalised; align sign before comparing direction.
    if np.dot(vec, raw) < 0:
        vec = -vec
    assert np.allclose(vec, raw, atol=1e-6)


@pytest.mark.parametrize("seed", range(20))
def test_katz_satisfies_fixed_point(seed):
    r = random.Random(seed)
    n = r.randint(4, 7)
    edges = [(u, v) for u in range(n) for v in range(u + 1, n) if r.random() < 0.5]
    g = fnx.Graph(); g.add_nodes_from(range(n)); g.add_edges_from(edges)
    if g.number_of_edges() == 0:
        pytest.skip("no edges")

    A = fnx.adjacency_matrix(g).toarray().astype(float)
    alpha, beta = 0.1, 1.0
    kc = fnx.katz_centrality_numpy(g, alpha=alpha, beta=beta)
    x = np.array([kc[i] for i in range(n)])
    # x is the normalised solution of x = alpha A x + beta*s for some scale s>0:
    # so (x - alpha A x) is a positive multiple of the all-ones vector.
    residual = x - alpha * A @ x
    # All components of the residual share the same sign and are ~equal in ratio.
    assert np.ptp(residual / residual.mean()) < 1e-6
