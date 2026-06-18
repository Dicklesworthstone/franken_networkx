"""Parity for is_semiconnected / attracting components + fiedler validity.

is_semiconnected and the attracting-component functions are deterministic and
checked against networkx directly. The fiedler vector, however, is NOT unique
when the second-smallest Laplacian eigenvalue is degenerate (multiplicity > 1):
any vector in that eigenspace is a valid fiedler vector, so exact-vector parity
with networkx is mathematically wrong to assert. Instead we check the VALIDITY
invariant — the fiedler vector lies in the lambda_2 eigenspace (its Rayleigh
quotient equals the algebraic connectivity) and is orthogonal to the all-ones
vector. This resolves the apparent fiedler "divergence" (br-r37-c1-193zq) as
expected non-uniqueness, not a defect.

No mocks: real fnx and real networkx.
"""

from __future__ import annotations

import random

import numpy as np
import pytest
import networkx as nx
import franken_networkx as fnx


def _digraph(seed):
    r = random.Random(seed)
    n = r.randint(5, 9)
    edges = [(u, v) for u in range(n) for v in range(n) if u != v and r.random() < 0.35]
    return fnx.DiGraph(edges), nx.DiGraph(edges)


@pytest.mark.parametrize("seed", range(40))
def test_semiconnected_and_attracting_parity(seed):
    fd, nd = _digraph(seed)
    assert fnx.is_semiconnected(fd) == nx.is_semiconnected(nd)
    assert fnx.number_attracting_components(fd) == nx.number_attracting_components(nd)
    fa = sorted(sorted(c) for c in fnx.attracting_components(fd))
    na = sorted(sorted(c) for c in nx.attracting_components(nd))
    assert fa == na


@pytest.mark.parametrize("seed", range(40))
def test_fiedler_vector_is_a_valid_lambda2_eigenvector(seed):
    r = random.Random(seed)
    n = r.randint(5, 9)
    edges = [(u, v) for u in range(n) for v in range(n)
             if u != v and r.random() < 0.35]
    ug = fnx.Graph([(u, v) for u, v in edges if u < v])
    nug = nx.Graph([(u, v) for u, v in edges if u < v])
    if not fnx.is_connected(ug) or ug.number_of_nodes() <= 2:
        pytest.skip("disconnected / trivial")

    lam2 = nx.algebraic_connectivity(nug)
    # fnx's algebraic connectivity (the eigenVALUE) is unambiguous → must match.
    assert abs(fnx.algebraic_connectivity(ug) - lam2) < 1e-6

    L = nx.laplacian_matrix(nug).toarray().astype(float)
    v = np.asarray(fnx.fiedler_vector(ug), dtype=float)
    # Orthogonal to the all-ones vector (mean ~ 0).
    assert abs(v.mean()) < 1e-6
    # Rayleigh quotient equals lambda_2 → v is in the fiedler eigenspace.
    vc = v - v.mean()
    rayleigh = (vc @ L @ vc) / (vc @ vc)
    assert abs(rayleigh - lam2) < 1e-5


def test_fiedler_nonuniqueness_is_handled_on_degenerate_graph():
    # The 4-cycle C4 has lambda_2 = 2 with multiplicity 2 — fiedler is non-unique,
    # but fnx still returns a valid one (Rayleigh quotient == 2).
    g = fnx.cycle_graph(4)
    L = nx.laplacian_matrix(nx.cycle_graph(4)).toarray().astype(float)
    v = np.asarray(fnx.fiedler_vector(g), dtype=float)
    vc = v - v.mean()
    assert abs((vc @ L @ vc) / (vc @ vc) - fnx.algebraic_connectivity(g)) < 1e-5
