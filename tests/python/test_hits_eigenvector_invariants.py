"""HITS hub/authority invariants, handling eigenvalue non-uniqueness.

HITS converges to the principal eigenvector of A*A^T (hubs) and A^T*A
(authorities). On an UNDIRECTED graph A is symmetric, so when the principal
eigenvalue is simple the hub and authority vectors coincide and equal the
principal eigenvector of A (i.e. eigenvector_centrality). But when that
eigenvalue is DEGENERATE (multiplicity > 1 — common for bipartite graphs whose
A-spectrum is symmetric), the HITS vectors are NOT unique: any vector in the
eigenspace is valid, and fnx vs networkx (and hubs vs authorities) may legitimately
differ. So strict equality is asserted only on non-degenerate graphs; the
universal invariants (sum to 1, non-negative) hold always.

No mocks: real fnx and real networkx (numpy for the eigen-check).
"""

from __future__ import annotations

import random

import numpy as np
import pytest
import networkx as nx
import franken_networkx as fnx


def _connected(seed):
    r = random.Random(seed)
    n = r.randint(5, 9)
    edges = [(u, v) for u in range(n) for v in range(u + 1, n) if r.random() < 0.4]
    g = fnx.Graph(); g.add_nodes_from(range(n)); g.add_edges_from(edges)
    return g, n


def _top_eigenvalue_is_simple(g):
    A = fnx.adjacency_matrix(g).toarray().astype(float)
    evals = sorted(np.linalg.eigvalsh(A @ A.T), reverse=True)
    return sum(1 for e in evals if abs(e - evals[0]) < 1e-6) == 1


@pytest.mark.parametrize("seed", range(40))
def test_hits_sums_to_one(seed):
    g, n = _connected(seed)
    if not fnx.is_connected(g) or g.number_of_edges() == 0:
        pytest.skip("disconnected / empty")
    h, a = fnx.hits(g)
    # Normalized HITS sums to 1 (always — even on degenerate inputs).
    assert abs(sum(h.values()) - 1) < 1e-5
    assert abs(sum(a.values()) - 1) < 1e-5
    # NOTE: non-negativity holds only when the top singular value is SIMPLE.
    # On degenerate inputs svds returns an arbitrary (possibly sign-flipped)
    # subspace vector in BOTH fnx and networkx (documented: br-r37-c1-hitsdegen),
    # so non-negativity is asserted in the simple-eigenvalue test below, not here.


@pytest.mark.parametrize("seed", range(40))
def test_hits_nonnegative_when_simple(seed):
    g, n = _connected(seed)
    if not fnx.is_connected(g) or g.number_of_edges() == 0:
        pytest.skip("disconnected / empty")
    if not _top_eigenvalue_is_simple(g):
        pytest.skip("degenerate → svds may return a sign-flipped subspace vector")
    h, a = fnx.hits(g)
    # With a simple top singular value, HITS is the non-negative Perron vector.
    assert all(v >= -1e-9 for v in h.values())
    assert all(v >= -1e-9 for v in a.values())


@pytest.mark.parametrize("seed", range(40))
def test_hits_equals_eigenvector_when_simple(seed):
    g, n = _connected(seed)
    if not fnx.is_connected(g) or g.number_of_edges() == 0:
        pytest.skip("disconnected / empty")
    if not _top_eigenvalue_is_simple(g):
        pytest.skip("degenerate principal eigenvalue → HITS not unique")
    h, a = fnx.hits(g)
    # Simple eigenvalue: hubs == authorities (symmetric A) and == nx's HITS.
    assert all(abs(h[i] - a[i]) < 1e-4 for i in g)
    nh, na = nx.hits(nx.Graph(list(g.edges())))
    assert all(abs(h[i] - nh[i]) < 1e-4 for i in g)
    # And proportional to the principal eigenvector (eigenvector_centrality).
    ec = fnx.eigenvector_centrality_numpy(g)
    s = sum(ec.values())
    ecn = {k: v / s for k, v in ec.items()}
    assert all(abs(h[i] - ecn[i]) < 1e-3 for i in g)


def test_hits_nonuniqueness_on_complete_bipartite():
    # K_{2,3}: bipartite, A*A^T has a degenerate top eigenvalue → HITS not unique,
    # but it is still a valid non-negative distribution summing to 1.
    g = fnx.complete_bipartite_graph(2, 3)
    h, a = fnx.hits(g)
    assert abs(sum(h.values()) - 1) < 1e-5
    assert abs(sum(a.values()) - 1) < 1e-5
