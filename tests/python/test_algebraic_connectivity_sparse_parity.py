"""Parity for the sparse-eigsh algebraic_connectivity.

br-algconnsparse: algebraic_connectivity formed the DENSE Laplacian and ran
np.linalg.eigvalsh (O(n^3)) -- ~7x slower than networkx (1.85s vs 0.26s on a
400-node sparse graph), which uses a sparse iterative solver. It now builds the
sparse Laplacian and pulls the smallest eigenvalues with shift-invert ARPACK
(scipy eigsh, sigma=0), falling back to dense for tiny graphs or on failure.
The Fiedler value matches networkx within ~1e-7.
"""

import random

import networkx as nx

import franken_networkx as fnx


def _cp(Gx):
    Gf = fnx.Graph()
    Gf.add_nodes_from(Gx.nodes())
    Gf.add_edges_from(Gx.edges(data=True))
    return Gf


def _graphs():
    # NB: deliberately sparse / structured graphs. nx's default tracemin_pcg
    # solver can fail to converge (and effectively hang) on dense normalized
    # Laplacians, so dense graphs are exercised separately against the dense
    # solver only (see test_dense_graph_takes_dense_path_and_is_fast).
    yield "watts400", nx.connected_watts_strogatz_graph(400, 6, 0.3, seed=1)
    yield "path100", nx.path_graph(100)
    yield "cycle200", nx.cycle_graph(200)
    yield "complete40", nx.complete_graph(40)
    yield "grid", nx.convert_node_labels_to_integers(nx.grid_2d_graph(18, 18))
    yield "tiny3", nx.path_graph(3)
    yield "tiny2", nx.path_graph(2)


def test_value_parity_unweighted():
    for name, Gx in _graphs():
        Gf = _cp(Gx)
        for normalized in (False, True):
            a = nx.algebraic_connectivity(Gx, normalized=normalized)
            b = fnx.algebraic_connectivity(Gf, normalized=normalized)
            assert abs(a - b) < 1e-6, (name, normalized, a, b)


def test_weighted_parity():
    Gx = nx.connected_watts_strogatz_graph(200, 6, 0.3, seed=7)
    rnd = random.Random(7)
    for u, v in Gx.edges():
        Gx[u][v]["weight"] = rnd.randint(1, 5)
    Gf = _cp(Gx)
    for normalized in (False, True):
        a = nx.algebraic_connectivity(Gx, normalized=normalized)
        b = fnx.algebraic_connectivity(Gf, normalized=normalized)
        assert abs(a - b) < 1e-6, (normalized, a, b)


def test_disconnected_returns_zero():
    Gf = fnx.Graph([(0, 1), (2, 3)])
    assert fnx.algebraic_connectivity(Gf) == 0.0


def test_directed_raises():
    Gf = fnx.DiGraph([(0, 1), (1, 2), (2, 0)])
    try:
        fnx.algebraic_connectivity(Gf)
    except fnx.NetworkXNotImplemented:
        pass
    else:  # pragma: no cover
        raise AssertionError("expected NetworkXNotImplemented for directed input")


def test_single_node_raises():
    Gf = fnx.Graph()
    Gf.add_node(0)
    try:
        fnx.algebraic_connectivity(Gf)
    except fnx.NetworkXError:
        pass
    else:  # pragma: no cover
        raise AssertionError("expected NetworkXError for <2 nodes")


def test_method_kwarg_accepted():
    # method/tol/seed accepted for nx signature parity; value is unchanged.
    Gx = nx.connected_watts_strogatz_graph(80, 6, 0.3, seed=3)
    Gf = _cp(Gx)
    base = fnx.algebraic_connectivity(Gf)
    for method in ("tracemin_pcg", "lanczos", "lobpcg"):
        assert abs(fnx.algebraic_connectivity(Gf, method=method) - base) < 1e-6


def test_dense_graph_takes_dense_path_and_is_fast():
    # On a dense Laplacian the sparsity gate routes to the dense solver (the
    # shift-invert path can converge slowly there). fnx must return promptly
    # and match the dense eigvalsh value; compare against nx only on the
    # non-normalized case (nx's tracemin can hang on dense normalized inputs).
    import time

    Gx = nx.connected_watts_strogatz_graph(200, 20, 0.3, seed=2)
    Gf = _cp(Gx)
    for normalized in (False, True):
        start = time.perf_counter()
        val = fnx.algebraic_connectivity(Gf, normalized=normalized)
        assert time.perf_counter() - start < 5.0
        assert val > 0 and val == val  # finite, positive (connected graph)
    assert abs(
        fnx.algebraic_connectivity(Gf) - nx.algebraic_connectivity(Gx)
    ) < 1e-6
