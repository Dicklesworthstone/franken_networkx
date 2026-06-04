"""Parity for the sparse-eigsh fiedler_vector.

br-fiedlersparse: fiedler_vector formed the DENSE Laplacian and ran
np.linalg.eigh (O(n^3)) -- the same ~6.5x tax as algebraic_connectivity. For a
sparse graph with a SIMPLE second-smallest eigenvalue it now gets the Fiedler
eigenpair with shift-invert ARPACK (scipy eigsh, sigma=0), ~90x faster. The
Fiedler vector is sign-ambiguous (nx and the old dense solver already disagree
on sign), so the result is a canonically-signed Fiedler eigenvector; degenerate
lambda2 / dense / tiny graphs fall back to the exact dense eigh.
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


def _is_fiedler(Gf, v):
    # v must be an eigenvector of the Laplacian for the algebraic connectivity.
    L = fnx.laplacian_matrix(Gf).toarray()
    v = np.asarray(v, dtype=float)
    lam = fnx.algebraic_connectivity(Gf)
    return np.linalg.norm(L @ v - lam * v) < 1e-5 * max(1.0, np.linalg.norm(v))


def _canon(v):
    v = np.asarray(v, dtype=float)
    j = int(np.argmax(np.abs(v)))
    return v if v[j] >= 0 else -v


def test_returns_valid_fiedler_vector():
    for name, Gx in [
        ("watts400", nx.connected_watts_strogatz_graph(400, 6, 0.3, seed=1)),
        ("path100", nx.path_graph(100)),
        ("grid", nx.convert_node_labels_to_integers(nx.grid_2d_graph(15, 15))),
        ("complete40", nx.complete_graph(40)),
        ("cycle100", nx.cycle_graph(100)),
        ("tiny5", nx.path_graph(5)),
    ]:
        Gf = _cp(Gx)
        assert _is_fiedler(Gf, fnx.fiedler_vector(Gf)), name


def test_nondegenerate_matches_nx_up_to_sign():
    for seed in (1, 2, 3):
        Gx = nx.connected_watts_strogatz_graph(200, 6, 0.3, seed=seed)
        Gf = _cp(Gx)
        assert np.allclose(
            _canon(nx.fiedler_vector(Gx)), _canon(fnx.fiedler_vector(Gf)), atol=1e-5
        ), seed


def test_weighted_valid():
    Gx = nx.connected_watts_strogatz_graph(150, 6, 0.3, seed=7)
    rnd = random.Random(7)
    for u, v in Gx.edges():
        Gx[u][v]["weight"] = rnd.randint(1, 5)
    Gf = _cp(Gx)
    assert _is_fiedler(Gf, fnx.fiedler_vector(Gf))


def test_normalized_valid():
    Gx = nx.connected_watts_strogatz_graph(120, 6, 0.3, seed=2)
    Gf = _cp(Gx)
    v = np.asarray(fnx.fiedler_vector(Gf, normalized=True), dtype=float)
    assert np.all(np.isfinite(v)) and v.shape[0] == 120


def test_directed_raises():
    Gf = fnx.DiGraph([(0, 1), (1, 2), (2, 0)])
    try:
        fnx.fiedler_vector(Gf)
    except fnx.NetworkXNotImplemented:
        pass
    else:  # pragma: no cover
        raise AssertionError("expected NetworkXNotImplemented for directed input")


def test_disconnected_raises():
    Gf = fnx.Graph([(0, 1), (2, 3)])
    try:
        fnx.fiedler_vector(Gf)
    except fnx.NetworkXError:
        pass
    else:  # pragma: no cover
        raise AssertionError("expected NetworkXError for disconnected input")
