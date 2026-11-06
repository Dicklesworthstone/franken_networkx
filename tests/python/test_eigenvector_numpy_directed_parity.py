"""Regression: eigenvector_centrality_numpy must use the LEFT eigenvector
(in-edge convention) on directed graphs, matching networkx.

networkx solves ``eigs(M.T, ...)`` — the left eigenvector — so a node's
eigenvector centrality reflects its in-edges. fnx previously solved ``eigs(A)``
(the right / out-edge eigenvector), so eigenvector_centrality_numpy returned the
wrong values on DiGraphs, disagreeing with both nx AND fnx's own iterative
eigenvector_centrality (which already uses the in-edge convention). For
undirected graphs A is symmetric so the transpose is a no-op. (br-r37-c1-evnumdir)
"""

import networkx as nx
import numpy as np
import franken_networkx as fnx
import scipy.sparse.linalg as sparse_linalg

import pytest


def _strongly_connected_digraph(mod, n, extra):
    g = mod.DiGraph()
    for i in range(n):
        g.add_edge(i, (i + 1) % n)  # ring guarantees strong connectivity
    for u, v in extra:
        g.add_edge(u, v)
    return g


def test_directed_eigenvector_numpy_matches_networkx():
    extra = [(0, 2), (2, 0), (1, 3), (3, 1), (0, 4)]
    gn = _strongly_connected_digraph(nx, 6, extra)
    gf = _strongly_connected_digraph(fnx, 6, extra)
    en = nx.eigenvector_centrality_numpy(gn)
    ef = fnx.eigenvector_centrality_numpy(gf)
    assert set(en) == set(ef)
    for k in en:
        assert abs(en[k] - ef[k]) <= 1e-9, f"node {k}: nx={en[k]} fnx={ef[k]}"


def test_directed_eigenvector_numpy_agrees_with_iterative():
    extra = [(0, 2), (2, 4), (4, 0), (1, 5)]
    gf = _strongly_connected_digraph(fnx, 6, extra)
    enum = fnx.eigenvector_centrality_numpy(gf)
    eiter = fnx.eigenvector_centrality(gf, max_iter=5000, tol=1e-12)
    for k in enum:
        assert abs(enum[k] - eiter[k]) <= 1e-6, f"node {k}: numpy={enum[k]} iter={eiter[k]}"


def test_weighted_directed_eigenvector_numpy_matches_networkx():
    def build(mod):
        g = mod.DiGraph()
        for i in range(6):
            g.add_edge(i, (i + 1) % 6, weight=float(i + 1))
        g.add_edge(0, 3, weight=2.0)
        return g
    en = nx.eigenvector_centrality_numpy(build(nx), weight="weight")
    ef = fnx.eigenvector_centrality_numpy(build(fnx), weight="weight")
    for k in en:
        assert abs(en[k] - ef[k]) <= 1e-9


@pytest.mark.parametrize("seed", [0, 1, 2, 3, 4])
def test_undirected_eigenvector_numpy_unchanged(seed):
    gn = nx.gnp_random_graph(10, 0.45, seed=seed)
    gf = fnx.gnp_random_graph(10, 0.45, seed=seed)
    if not nx.is_connected(gn):
        pytest.skip("disconnected")
    en = nx.eigenvector_centrality_numpy(gn)
    ef = fnx.eigenvector_centrality_numpy(gf)
    for k in en:
        assert abs(en[k] - ef[k]) <= 1e-9


@pytest.mark.parametrize("graph_type", ["Graph", "DiGraph"])
@pytest.mark.parametrize("scale", [1.0, 17.0, 1e-20, 1e20])
def test_signed_eigenvector_retains_relative_signs_and_eigenpair(graph_type, scale):
    """Taking componentwise magnitudes no longer gives an eigenvector."""
    edges = [("a", "b", -2.0), ("b", "c", 1.0)]
    eigenvalue = np.sqrt(5.0) * scale
    if graph_type == "DiGraph":
        edges = [("a", "b", -2.0), ("b", "c", -3.0), ("c", "a", 4.0)]
        eigenvalue = np.cbrt(24.0) * scale

    expected_graph = getattr(nx, graph_type)()
    actual_graph = getattr(fnx, graph_type)()
    for graph in (expected_graph, actual_graph):
        graph.add_nodes_from(["c", "a", "b"])
        graph.add_weighted_edges_from((u, v, w * scale) for u, v, w in edges)

    expected = nx.eigenvector_centrality_numpy(expected_graph, weight="weight")
    actual = fnx.eigenvector_centrality_numpy(actual_graph, weight="weight")
    assert list(actual) == list(expected_graph)
    assert actual == pytest.approx(expected, rel=1e-10, abs=1e-12)
    vector = np.array([actual[node] for node in expected_graph])
    assert np.linalg.norm(vector) == pytest.approx(1.0)
    assert vector.sum() > 0
    assert (vector < 0).any()
    matrix = nx.to_numpy_array(expected_graph, weight="weight")
    np.testing.assert_allclose(
        matrix.T @ vector,
        eigenvalue * vector,
        rtol=1e-10,
        atol=abs(eigenvalue) * 1e-12,
    )


@pytest.mark.parametrize("orientation", [-1.0, 1.0])
def test_eigenvector_global_sign_is_independent_of_solver_orientation(monkeypatch, orientation):
    expected_vector = np.array([-2.0, np.sqrt(5.0), 1.0]) / np.sqrt(10.0)

    def eigenpair(*args, **kwargs):
        return np.array([np.sqrt(5.0)]), (orientation * expected_vector).reshape(3, 1)

    monkeypatch.setattr(sparse_linalg, "eigs", eigenpair)
    expected_graph = nx.Graph()
    actual_graph = fnx.Graph()
    for graph in (expected_graph, actual_graph):
        graph.add_weighted_edges_from([(0, 1, -2.0), (1, 2, 1.0)])
    expected = nx.eigenvector_centrality_numpy(expected_graph, weight="weight")
    actual = fnx.eigenvector_centrality_numpy(actual_graph, weight="weight")
    assert actual == pytest.approx(expected)
    np.testing.assert_allclose(list(actual.values()), expected_vector)


@pytest.mark.parametrize("graph_type", ["Graph", "DiGraph"])
@pytest.mark.parametrize("weight_scale", [10**30, 10**200])
def test_eigenvector_casts_large_integer_weights_before_sparse_construction(
    graph_type, weight_scale
):
    edges = [(0, 1, 2 * weight_scale), (1, 2, weight_scale)]
    if graph_type == "DiGraph":
        edges.append((2, 0, 3 * weight_scale))
    expected_graph = getattr(nx, graph_type)()
    actual_graph = getattr(fnx, graph_type)()
    for graph in (expected_graph, actual_graph):
        graph.add_weighted_edges_from(edges)
    expected = nx.eigenvector_centrality_numpy(expected_graph, weight="weight")
    actual = fnx.eigenvector_centrality_numpy(actual_graph, weight="weight")
    assert actual == pytest.approx(expected, rel=1e-10, abs=1e-12)


def test_eigenvector_preserves_nonconvergence_and_partial_results(monkeypatch):
    eigenvalues = np.array([0.5])
    eigenvectors = np.array([[1.0], [0.0], [0.0], [0.0]])
    failure = sparse_linalg.ArpackNoConvergence(
        "iteration budget exhausted", eigenvalues, eigenvectors
    )
    calls = []

    def fail_to_converge(matrix, **kwargs):
        calls.append(kwargs)
        raise failure

    monkeypatch.setattr(sparse_linalg, "eigs", fail_to_converge)
    for module in (nx, fnx):
        graph = module.path_graph(4)
        with pytest.raises(sparse_linalg.ArpackNoConvergence) as raised:
            module.eigenvector_centrality_numpy(graph, max_iter=1, tol=1e-14)
        assert raised.value is failure
        assert raised.value.eigenvalues is eigenvalues
        assert raised.value.eigenvectors is eigenvectors
    assert calls == [
        {"k": 1, "which": "LR", "maxiter": 1, "tol": 1e-14},
        {"k": 1, "which": "LR", "maxiter": 1, "tol": 1e-14},
    ]


@pytest.mark.parametrize("graph_type", ["Graph", "DiGraph"])
@pytest.mark.parametrize("node_count", [1, 2])
def test_eigenvector_small_graph_solver_error_matches_networkx(graph_type, node_count):
    errors = []
    for module in (nx, fnx):
        graph = getattr(module, graph_type)()
        graph.add_nodes_from(range(node_count))
        for node in range(node_count):
            graph.add_edge(node, (node + 1) % node_count)
        with pytest.warns(RuntimeWarning, match="k >= N - 1"):
            with pytest.raises(TypeError) as raised:
                module.eigenvector_centrality_numpy(graph)
        errors.append(str(raised.value))
    assert errors[0] == errors[1]


@pytest.mark.parametrize("max_iter", [0, float("nan")])
@pytest.mark.parametrize("empty", [True, False])
def test_eigenvector_graph_errors_precede_solver_parameter_errors(max_iter, empty):
    errors = []
    for module in (nx, fnx):
        graph = module.Graph()
        if not empty:
            graph.add_nodes_from([0, 1, 2])
        expected_error = module.NetworkXPointlessConcept if empty else module.AmbiguousSolution
        with pytest.raises(expected_error) as raised:
            module.eigenvector_centrality_numpy(graph, max_iter=max_iter)
        errors.append(str(raised.value))
    assert errors[0] == errors[1]
