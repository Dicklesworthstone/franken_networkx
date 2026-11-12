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

Everything above is about UNDIRECTED graphs, where A is symmetric and hubs and
authorities coincide — which is the one setting in which HITS's defining feature
disappears. HITS is a directed algorithm: a hub points at good authorities and an
authority is pointed at by good hubs, so the two vectors differ, and they satisfy
the mutual-reinforcement fixed point

    authorities = normalize(A^T . hubs)       hubs = normalize(A . authorities)

That fixed point, and the degenerate-free closed forms of a pure hub and a pure
authority, are pinned below on digraphs.

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


def _digraph(seed):
    r = random.Random(seed)
    n = r.randint(5, 8)
    d = fnx.DiGraph(); d.add_nodes_from(range(n))
    for u in range(n):
        for v in range(n):
            if u != v and r.random() < 0.3:
                d.add_edge(u, v)
    return d, n


@pytest.mark.parametrize("seed", range(30))
def test_directed_hits_satisfies_mutual_reinforcement(seed):
    """The defining fixed point, which an undirected graph cannot exhibit."""
    d, n = _digraph(seed)
    hubs, auth = fnx.hits(d)
    order = list(d.nodes())
    A = fnx.adjacency_matrix(d).toarray().astype(float)
    h = np.array([hubs[v] for v in order])
    a = np.array([auth[v] for v in order])

    # Unconditional, degenerate inputs included.
    assert abs(h.sum() - 1) < 1e-5 and abs(a.sum() - 1) < 1e-5
    if _top_eigenvalue_is_simple(d):
        # Non-negativity is NOT unconditional: with a degenerate top eigenvalue
        # svds returns an arbitrary subspace vector, which may carry negative
        # entries (measured: 0 of the 28 simple draws, 1 of the 2 degenerate
        # ones). Same rule the undirected tests above already apply.
        assert all(v >= -1e-9 for v in h) and all(v >= -1e-9 for v in a)

    # authorities are the normalized in-flow from hubs, and vice versa.
    from_hubs = A.T @ h
    from_auth = A @ a
    assert np.allclose(from_hubs / from_hubs.sum(), a, atol=1e-4)
    assert np.allclose(from_auth / from_auth.sum(), h, atol=1e-4)


def test_directed_hubs_and_authorities_actually_differ():
    """Guards the sweep: on undirected input the two vectors are equal by
    construction, so a directed family that failed to separate them would make
    the fixed-point test far weaker than it looks."""
    separated = 0
    for seed in range(30):
        d, _ = _digraph(seed)
        hubs, auth = fnx.hits(d)
        if any(abs(hubs[v] - auth[v]) > 1e-4 for v in d):
            separated += 1
    assert separated >= 20, f"only {separated} of 30 digraphs separate hubs from authorities"


def test_pure_hub_and_pure_authority_closed_forms():
    """A star's centre is all hub and no authority, and reversing swaps the roles."""
    out_star = fnx.DiGraph(); out_star.add_edges_from([(0, 1), (0, 2), (0, 3)])
    hubs, auth = fnx.hits(out_star)
    assert abs(hubs[0] - 1.0) < 1e-6                       # sole hub
    assert all(abs(hubs[v]) < 1e-6 for v in (1, 2, 3))
    assert abs(auth[0]) < 1e-6                             # points at nobody's target
    assert all(abs(auth[v] - 1 / 3) < 1e-6 for v in (1, 2, 3))

    in_star = fnx.DiGraph(); in_star.add_edges_from([(1, 0), (2, 0), (3, 0)])
    hubs, auth = fnx.hits(in_star)
    assert abs(auth[0] - 1.0) < 1e-6                       # sole authority
    assert all(abs(hubs[v] - 1 / 3) < 1e-6 for v in (1, 2, 3))
    assert abs(hubs[0]) < 1e-6


def test_hits_nonuniqueness_on_complete_bipartite():
    # K_{2,3}: bipartite, A*A^T has a degenerate top eigenvalue → HITS not unique,
    # but it is still a valid non-negative distribution summing to 1.
    g = fnx.complete_bipartite_graph(2, 3)
    h, a = fnx.hits(g)
    assert abs(sum(h.values()) - 1) < 1e-5
    assert abs(sum(a.values()) - 1) < 1e-5
