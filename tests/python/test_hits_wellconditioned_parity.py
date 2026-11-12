"""br-r37-c1-a0466 / br-r37-c1-6fem6 resolution: HITS parity contract.

fnx.hits and nx.hits use the IDENTICAL algorithm (scipy.sparse.linalg.svds
on the adjacency matrix, then h = A @ a, sum-normalized). On graphs whose
top singular value is SIMPLE, the dominant singular vector is unique up to
sign and both impls match at machine precision (asserted below).

On graphs with a DEGENERATE top singular value (e.g. bipartite or many
regular graphs — singular value multiplicity > 1), the dominant singular
vector is non-unique; scipy's svds picks an arbitrary vector from the
subspace via a random v0, so BOTH fnx.hits AND nx.hits vary run-to-run
(nx can even return negative values). That is intrinsic scipy
non-determinism, not a parity gap — there is nothing to match. This test
gates on a simple top singular value so it is deterministic.
"""
import random

import networkx as nx
import numpy as np
import pytest

import franken_networkx as fnx


def _simple_top(g):
    A = nx.adjacency_matrix(g, nodelist=list(g), dtype=float).todense()
    sv = np.linalg.svd(np.asarray(A))[1]
    return len(sv) >= 2 and sv[0] - sv[1] > 1e-6


def _well_conditioned_graphs():
    rnd = random.Random(21)
    out = []
    trial = 0
    while len(out) < 25 and trial < 400:
        trial += 1
        n = rnd.randrange(5, 30)
        edges = [
            (u, v)
            for u, v in ((rnd.randrange(n), rnd.randrange(n)) for _ in range(rnd.randrange(n, n * 3)))
            if u != v
        ]
        gn = nx.Graph(edges)
        if gn.number_of_nodes() < 3 or not nx.is_connected(gn) or nx.is_bipartite(gn):
            continue
        if not _simple_top(gn):
            continue
        out.append(edges)
    return out


@pytest.mark.parametrize("edges", _well_conditioned_graphs())
def test_hits_matches_nx_on_well_conditioned_graphs(edges):
    gf, gn = fnx.Graph(edges), nx.Graph(edges)
    hf, af = fnx.hits(gf)
    hn, an = nx.hits(gn)
    assert {repr(k): round(v, 7) for k, v in hf.items()} == {
        repr(k): round(v, 7) for k, v in hn.items()
    }
    assert {repr(k): round(v, 7) for k, v in af.items()} == {
        repr(k): round(v, 7) for k, v in an.items()
    }


def test_hits_known_triangle():
    # Simplest non-bipartite: uniform hubs/authorities, deterministic.
    gf, gn = fnx.Graph([(0, 1), (1, 2), (0, 2)]), nx.Graph([(0, 1), (1, 2), (0, 2)])
    hf, af = fnx.hits(gf)
    hn, an = nx.hits(gn)
    assert {k: round(v, 7) for k, v in af.items()} == {k: round(v, 7) for k, v in an.items()}
    assert all(abs(v - 1 / 3) < 1e-6 for v in af.values())
