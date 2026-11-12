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

Both sweeps use undirected graphs, where A is symmetric and A and A^T are the
same matrix — so the file cannot see WHICH of the two the implementation uses.
On a digraph they differ, and Katz measures influence flowing IN: the resolvent
is (I - alpha A^T)^{-1}, which matches 20 of 20 directed draws where plain A
matches none. "For alpha below 1/lambda_max this is well defined" is the other
untested clause; above that bound the iteration provably cannot converge, and
that boundary is pinned too.

No mocks: real fnx (numpy for the linear algebra).
"""

from __future__ import annotations

import random

import numpy as np
import pytest
import franken_networkx as fnx

_ALPHA = 0.1
_BETA = 1.0


def _digraph(seed):
    r = random.Random(seed)
    n = r.randint(4, 7)
    d = fnx.DiGraph(); d.add_nodes_from(range(n))
    for u in range(n):
        for v in range(n):
            if u != v and r.random() < 0.35:
                d.add_edge(u, v)
    return d, n


def _aligned(vec, reference):
    """Katz vectors are normalised; align sign before comparing direction."""
    return -vec if np.dot(vec, reference) < 0 else vec


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


@pytest.mark.parametrize("seed", range(20))
def test_directed_katz_uses_the_transpose(seed):
    """A and A^T coincide on the undirected sweeps, so the convention was free."""
    d, n = _digraph(seed)
    if d.number_of_edges() == 0:
        pytest.skip("no edges")

    A = fnx.adjacency_matrix(d).toarray().astype(float)
    kc = fnx.katz_centrality_numpy(d, alpha=_ALPHA, beta=_BETA)
    vec = np.array([kc[i] for i in range(n)])

    transposed = np.linalg.solve(np.eye(n) - _ALPHA * A.T, _BETA * np.ones(n))
    transposed /= np.linalg.norm(transposed)
    assert np.allclose(_aligned(vec, transposed), transposed, atol=1e-6)

    # Discriminating: plain A is a genuinely different vector once A is asymmetric.
    if not np.allclose(A, A.T):
        plain = np.linalg.solve(np.eye(n) - _ALPHA * A, _BETA * np.ones(n))
        plain /= np.linalg.norm(plain)
        assert not np.allclose(_aligned(vec, plain), plain, atol=1e-6)


def test_directed_family_is_actually_asymmetric():
    """Guards the test above: a symmetric draw would make A and A^T agree."""
    asymmetric = 0
    for seed in range(20):
        d, _ = _digraph(seed)
        A = fnx.adjacency_matrix(d).toarray().astype(float)
        if d.number_of_edges() and not np.allclose(A, A.T):
            asymmetric += 1
    assert asymmetric >= 15, f"only {asymmetric} of 20 directed draws are asymmetric"


@pytest.mark.parametrize("seed", range(20))
def test_iterative_and_numpy_solvers_agree(seed):
    """katz_centrality iterates; katz_centrality_numpy solves. Same answer."""
    r = random.Random(seed)
    n = r.randint(4, 7)
    edges = [(u, v) for u in range(n) for v in range(u + 1, n) if r.random() < 0.5]
    g = fnx.Graph(); g.add_nodes_from(range(n)); g.add_edges_from(edges)
    if g.number_of_edges() == 0:
        pytest.skip("no edges")

    iterative = fnx.katz_centrality(g, alpha=_ALPHA, beta=_BETA)
    direct = fnx.katz_centrality_numpy(g, alpha=_ALPHA, beta=_BETA)
    assert all(abs(iterative[v] - direct[v]) < 1e-6 for v in g)


def test_alpha_must_stay_below_the_spectral_bound():
    """The docstring's "for alpha below 1/lambda_max" clause, both sides of it."""
    g = fnx.gnm_random_graph(8, 14, seed=3)
    A = fnx.adjacency_matrix(g).toarray().astype(float)
    lambda_max = max(np.linalg.eigvalsh(A))

    # Comfortably inside the radius of convergence: the iteration converges.
    fnx.katz_centrality(g, alpha=0.9 / lambda_max)

    # Outside it, the Neumann series diverges and the iteration cannot converge.
    with pytest.raises(fnx.PowerIterationFailedConvergence):
        fnx.katz_centrality(g, alpha=1.5 / lambda_max)


@pytest.mark.parametrize("seed", range(20))
def test_beta_may_be_a_per_node_vector(seed):
    """beta is the source term; a dict makes it non-uniform."""
    r = random.Random(seed)
    n = r.randint(4, 7)
    edges = [(u, v) for u in range(n) for v in range(u + 1, n) if r.random() < 0.5]
    g = fnx.Graph(); g.add_nodes_from(range(n)); g.add_edges_from(edges)
    if g.number_of_edges() == 0:
        pytest.skip("no edges")

    beta = {v: (2.0 if v == 0 else 1.0) for v in g}
    kc = fnx.katz_centrality_numpy(g, alpha=_ALPHA, beta=beta)
    vec = np.array([kc[i] for i in range(n)])

    A = fnx.adjacency_matrix(g).toarray().astype(float)
    source = np.array([beta[i] for i in range(n)])
    raw = np.linalg.solve(np.eye(n) - _ALPHA * A.T, source)
    raw /= np.linalg.norm(raw)
    assert np.allclose(_aligned(vec, raw), raw, atol=1e-6)
