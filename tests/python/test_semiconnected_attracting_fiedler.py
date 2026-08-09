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


def test_disconnected_contracts_are_not_uniform():
    """What the sweep's skip discards — and the two functions disagree there.

    On a disconnected graph lambda_2 is 0, so there is no meaningful Fiedler
    direction: fiedler_vector refuses, while algebraic_connectivity simply
    reports 0.0. Easy to assume a spectral pair behaves alike; it does not.
    """
    fg = fnx.Graph([(0, 1), (2, 3)])
    ng = nx.Graph([(0, 1), (2, 3)])

    with pytest.raises(fnx.NetworkXError):
        fnx.fiedler_vector(fg)
    with pytest.raises(nx.NetworkXError):
        nx.fiedler_vector(ng)

    assert fnx.algebraic_connectivity(fg) == 0.0
    assert fnx.algebraic_connectivity(fg) == nx.algebraic_connectivity(ng)


@pytest.mark.parametrize("method", ["tracemin_pcg", "tracemin_lu", "lanczos"])
def test_eigensolver_methods_agree(method):
    """Three different algorithms for one eigenvalue; none was ever selected.

    They must agree with each other and with networkx — a cross-method check
    that parity against a single default cannot provide.
    """
    fg = fnx.gnm_random_graph(9, 18, seed=4)
    ng = nx.gnm_random_graph(9, 18, seed=4)

    value = fnx.algebraic_connectivity(fg, method=method)
    assert abs(value - nx.algebraic_connectivity(ng, method=method)) < 1e-6
    # ...and the same number the default method produces.
    assert abs(value - fnx.algebraic_connectivity(fg)) < 1e-6


def test_normalized_and_weight_parameters_are_read():
    """Both change the operator, and parity alone cannot see them ignored."""
    fg = fnx.gnm_random_graph(9, 18, seed=4)
    ng = nx.gnm_random_graph(9, 18, seed=4)

    normalized = fnx.algebraic_connectivity(fg, normalized=True)
    assert abs(normalized - nx.algebraic_connectivity(ng, normalized=True)) < 1e-6
    assert abs(normalized - fnx.algebraic_connectivity(fg)) > 1e-9   # genuinely different

    weighted_f, weighted_n = fnx.Graph(), nx.Graph()
    for u, v, w in [(0, 1, 5), (1, 2, 1), (2, 3, 9), (3, 0, 1), (0, 2, 3)]:
        weighted_f.add_edge(u, v, weight=w)
        weighted_n.add_edge(u, v, weight=w)

    weighted = fnx.algebraic_connectivity(weighted_f, weight="weight")
    assert abs(weighted - nx.algebraic_connectivity(weighted_n, weight="weight")) < 1e-6
    assert abs(weighted - fnx.algebraic_connectivity(weighted_f, weight=None)) > 1e-9
