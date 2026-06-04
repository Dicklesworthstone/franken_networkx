"""Parity for the sparse-solve katz_centrality_numpy.

br-katzsparse: katz_centrality_numpy built the DENSE adjacency and ran
np.linalg.solve (dense O(n^3)) -- catastrophic on large sparse graphs
(n=1200: ~3.5s, ~110x slower than it needs to be). The Katz system
(I - alpha * A.T) x = b is sparse for a sparse graph; it now solves it with a
sparse LU (scipy spsolve), identical to machine precision, with a dense
fallback. Matches networkx within 1e-8.
"""

import random

import numpy as np
import networkx as nx

import franken_networkx as fnx


def _cp(Gx):
    Gf = fnx.Graph()
    Gf.add_nodes_from(Gx.nodes())
    Gf.add_edges_from(Gx.edges(data=True))
    return Gf


def _close(a, b, tol=1e-8):
    return set(a) == set(b) and all(abs(a[k] - b[k]) <= tol for k in a)


def test_parameter_matrix():
    for n, normalized, weight, seed in [
        (150, True, None, 1),
        (150, False, None, 2),
        (100, True, "weight", 3),
        (80, True, None, 5),
    ]:
        Gx = nx.connected_watts_strogatz_graph(n, 6, 0.3, seed=seed)
        if weight:
            rnd = random.Random(seed)
            for u, v in Gx.edges():
                Gx[u][v]["weight"] = rnd.randint(1, 5)
        Gf = _cp(Gx)
        assert _close(
            nx.katz_centrality_numpy(Gx, normalized=normalized, weight=weight),
            fnx.katz_centrality_numpy(Gf, normalized=normalized, weight=weight),
        ), (n, normalized, weight)


def test_beta_dict():
    Gx = nx.connected_watts_strogatz_graph(80, 6, 0.3, seed=7)
    rnd = random.Random(7)
    beta = {i: rnd.uniform(0.5, 2.0) for i in Gx.nodes()}
    Gf = _cp(Gx)
    assert _close(
        nx.katz_centrality_numpy(Gx, beta=beta),
        fnx.katz_centrality_numpy(Gf, beta=beta),
    )


def test_beta_dict_missing_node_raises():
    Gf = fnx.Graph([(0, 1), (1, 2)])
    try:
        fnx.katz_centrality_numpy(Gf, beta={0: 1.0, 1: 1.0})  # missing node 2
    except fnx.NetworkXError:
        pass
    else:  # pragma: no cover
        raise AssertionError("expected NetworkXError for incomplete beta dict")


def test_empty_graph():
    assert fnx.katz_centrality_numpy(fnx.Graph()) == {}


def test_multigraph_raises():
    try:
        fnx.katz_centrality_numpy(fnx.MultiGraph([(0, 1)]))
    except fnx.NetworkXNotImplemented:
        pass
    else:  # pragma: no cover
        raise AssertionError("expected NetworkXNotImplemented for multigraph")


def test_large_graph_parity_and_finite():
    Gx = nx.connected_watts_strogatz_graph(400, 6, 0.3, seed=99)
    Gf = _cp(Gx)
    result = fnx.katz_centrality_numpy(Gf)
    assert all(np.isfinite(v) for v in result.values())
    assert _close(nx.katz_centrality_numpy(Gx), result)
