"""Spectral / matrix parity with networkx.

Laplacian, normalized-Laplacian, adjacency and incidence matrices must match
networkx exactly, and the spectra / algebraic connectivity (order-invariant
scalars) must agree numerically.

NOTE: both libraries build their matrices in node-iteration order, so the
graphs MUST be constructed with identical node order — ``add_nodes_from(
range(n))`` before the edges in BOTH. Building one side as
``nx.Graph(edge_list)`` would introduce nodes in edge order, permuting its
matrix and producing a false mismatch (the eigenvalues would still agree —
that permutation-similarity is the tell). This test avoids that artifact.

No mocks: real fnx and real networkx on identically-constructed graphs.
"""

from __future__ import annotations

import random

import numpy as np
import pytest
import networkx as nx
import franken_networkx as fnx


def _identical_pair(seed):
    r = random.Random(seed)
    n = r.randint(5, 10)
    edges = [(u, v) for u in range(n) for v in range(u + 1, n) if r.random() < 0.5]
    fg = fnx.Graph(); fg.add_nodes_from(range(n)); fg.add_edges_from(edges)
    ng = nx.Graph(); ng.add_nodes_from(range(n)); ng.add_edges_from(edges)
    return fg, ng, n


@pytest.mark.parametrize("seed", range(30))
def test_matrices_match_networkx(seed):
    fg, ng, n = _identical_pair(seed)
    assert np.allclose(fnx.adjacency_matrix(fg).toarray(), nx.adjacency_matrix(ng).toarray())
    assert np.allclose(fnx.laplacian_matrix(fg).toarray(), nx.laplacian_matrix(ng).toarray())
    assert np.allclose(
        fnx.incidence_matrix(fg).toarray(), nx.incidence_matrix(ng).toarray()
    )
    if fnx.is_connected(fg):
        assert np.allclose(
            fnx.normalized_laplacian_matrix(fg).toarray(),
            nx.normalized_laplacian_matrix(ng).toarray(),
        )


@pytest.mark.parametrize("seed", range(30))
def test_spectra_and_algebraic_connectivity(seed):
    fg, ng, n = _identical_pair(seed)
    assert np.allclose(
        sorted(np.real(fnx.laplacian_spectrum(fg))),
        sorted(np.real(nx.laplacian_spectrum(ng))),
        atol=1e-6,
    )
    assert np.allclose(
        sorted(np.real(fnx.adjacency_spectrum(fg))),
        sorted(np.real(nx.adjacency_spectrum(ng))),
        atol=1e-6,
    )
    if fnx.is_connected(fg):
        assert abs(
            fnx.algebraic_connectivity(fg) - nx.algebraic_connectivity(ng)
        ) < 1e-6

    # br-r37-c1-iu2nm: the `sorted(...)` above is NOT an oversight and must not
    # be "tightened" to raw order. Sorted-VALUE is the ruled contract for the
    # spectra (br-r37-c1-spectrum-sorted-value): the raw LAPACK eigenvalue order
    # is not part of the API, so asserting it would pin an implementation
    # detail of the eigensolver. This note exists because every other blind
    # `sorted()` in these parity modules HAS been a real gap, and the next
    # reader should not assume this one is too.


def _weighted_pair(seed):
    """Same construction, but every edge carries a weight.

    br-r37-c1-iu2nm: the fixture above is entirely UNWEIGHTED, so the weighted
    matrix path — a different code route for all four matrices — was never
    exercised by this module.
    """
    r = random.Random(seed)
    n = r.randint(5, 10)
    fg = fnx.Graph(); fg.add_nodes_from(range(n))
    ng = nx.Graph(); ng.add_nodes_from(range(n))
    for u in range(n):
        for v in range(u + 1, n):
            if r.random() < 0.5:
                w = r.randint(1, 9)
                fg.add_edge(u, v, weight=w)
                ng.add_edge(u, v, weight=w)
    return fg, ng, n


_MATRICES = ["adjacency_matrix", "laplacian_matrix", "incidence_matrix"]


@pytest.mark.parametrize("builder", [_identical_pair, _weighted_pair])
@pytest.mark.parametrize("seed", range(30))
def test_matrices_are_bit_exact_not_merely_close(seed, builder):
    """br-r37-c1-iu2nm: this bead asks for EXACT matrix parity and the module
    asserted ``np.allclose``, which would accept a 1e-9 divergence. All four
    matrices are bit-identical to networkx — including the float-valued
    normalized Laplacian, verified 54/54 on connected graphs across both
    weighted and unweighted fixtures — so exact equality is achievable and is
    what the project's identical-FP-bits rule asks for. dtype and shape are
    compared too: a matrix that is numerically right in the wrong dtype passes
    every value comparison.
    """
    fg, ng, _ = builder(seed)
    for name in _MATRICES:
        got = getattr(fnx, name)(fg).toarray()
        want = getattr(nx, name)(ng).toarray()
        assert got.shape == want.shape, name
        assert got.dtype == want.dtype, name
        assert np.array_equal(got, want), name
    if fnx.is_connected(fg):
        got = fnx.normalized_laplacian_matrix(fg).toarray()
        want = nx.normalized_laplacian_matrix(ng).toarray()
        assert got.dtype == want.dtype
        assert np.array_equal(got, want)


@pytest.mark.parametrize("builder", [_identical_pair, _weighted_pair])
@pytest.mark.parametrize("seed", range(30))
def test_matrix_nodelist_permutation_parity(seed, builder):
    """br-r37-c1-iu2nm: `nodelist` permutes the matrix basis and is a distinct
    code path that nothing here reached. A reversed nodelist is the sharpest
    cheap case — it changes every row and column position.
    """
    fg, ng, n = builder(seed)
    order = list(range(n))[::-1]
    for name in ("adjacency_matrix", "laplacian_matrix"):
        got = getattr(fnx, name)(fg, nodelist=order).toarray()
        want = getattr(nx, name)(ng, nodelist=order).toarray()
        assert np.array_equal(got, want), name


def _spectral_preprocessing_pair(graph_class, route, weight, edge_weights, loops=False):
    oracle = getattr(nx, graph_class)()
    oracle.add_nodes_from(["tail", "left", "center", "right"])
    edges = [("left", "center"), ("center", "right"), ("right", "tail")]
    for (u, v), value in zip(edges, edge_weights):
        oracle.add_edges_from([(u, v, {weight: value})])
        if graph_class == "MultiGraph":
            oracle.add_edges_from([(u, v, {weight: -value})])
    if loops:
        oracle.add_edges_from((node, node, {weight: -1000}) for node in oracle)
    graph = oracle.copy() if route == "networkx" else getattr(fnx, graph_class)(oracle)
    return graph, oracle


def _assert_spectral_eigenpair(graph, oracle, canonical, weight, normalized):
    options = dict(weight=weight, normalized=normalized, method="tracemin_lu", seed=7)
    expected = nx.algebraic_connectivity(oracle, **options)
    assert fnx.algebraic_connectivity(graph, **options) == pytest.approx(expected, abs=1e-7)
    matrix = (
        nx.normalized_laplacian_matrix(canonical)
        if normalized else nx.laplacian_matrix(canonical)
    ).toarray()
    vector = np.asarray(fnx.fiedler_vector(graph, **options))
    assert vector.shape == (len(graph),)
    assert np.linalg.norm(vector) > 0
    assert np.linalg.norm(matrix @ vector - expected * vector) < 1e-7


@pytest.mark.parametrize("route", ["fnx", "networkx"])
@pytest.mark.parametrize("graph_class", ["Graph", "MultiGraph"])
@pytest.mark.parametrize("normalized", [False, True])
@pytest.mark.parametrize("weight", ["weight", "capacity", None, ("cost", 0)])
def test_spectral_preprocessing_signed_and_parallel_weights(route, graph_class, normalized, weight):
    graph, oracle = _spectral_preprocessing_pair(graph_class, route, weight, [-2, 3, -4])
    before = [(u, v, dict(data)) for u, v, data in graph.edges(data=True)]
    canonical = nx.Graph()
    canonical.add_nodes_from(oracle)
    values = [2, 3, 4] if graph_class == "Graph" else [4, 6, 8]
    canonical.add_weighted_edges_from([
        ("left", "center", values[0]),
        ("center", "right", values[1]),
        ("right", "tail", values[2]),
    ])
    _assert_spectral_eigenpair(graph, oracle, canonical, weight, normalized)
    options = dict(weight=weight, normalized=normalized, method="tracemin_lu", seed=7)
    assert fnx.spectral_ordering(graph, **options) == nx.spectral_ordering(oracle, **options)
    assert {frozenset(part) for part in fnx.spectral_bisection(graph, **options)} == {
        frozenset(part) for part in nx.spectral_bisection(oracle, **options)
    }
    assert list(graph) == list(oracle)
    assert list(graph.edges(data=True)) == before


@pytest.mark.parametrize("route", ["fnx", "networkx"])
@pytest.mark.parametrize("graph_class", ["Graph", "MultiGraph"])
@pytest.mark.parametrize("normalized", [False, True])
@pytest.mark.parametrize("weight", ["weight", "capacity", None, ("cost", 0)])
def test_spectral_preprocessing_zero_weight_bridge_is_disconnected(route, graph_class, normalized, weight):
    graph, oracle = _spectral_preprocessing_pair(graph_class, route, weight, [2, 0, 3])
    options = dict(weight=weight, normalized=normalized, method="tracemin_lu", seed=7)
    assert nx.algebraic_connectivity(oracle, **options) == 0.0
    assert fnx.algebraic_connectivity(graph, **options) == 0.0
    for name in ("fiedler_vector", "spectral_bisection"):
        with pytest.raises(nx.NetworkXError, match="graph is not connected"):
            getattr(nx, name)(oracle, **options)
        with pytest.raises(fnx.NetworkXError, match="graph is not connected"):
            getattr(fnx, name)(graph, **options)
    assert fnx.spectral_ordering(graph, **options) == nx.spectral_ordering(oracle, **options)


@pytest.mark.parametrize("route", ["fnx", "networkx"])
@pytest.mark.parametrize("graph_class", ["Graph", "MultiGraph"])
@pytest.mark.parametrize("weight", ["weight", "capacity", None, ("cost", 0)])
def test_spectral_preprocessing_ignores_self_loops_in_normalized_problem(route, graph_class, weight):
    graph, oracle = _spectral_preprocessing_pair(graph_class, route, weight, [2, 3, 4], loops=True)
    canonical = nx.Graph()
    canonical.add_nodes_from(oracle)
    values = [2, 3, 4] if graph_class == "Graph" else [4, 6, 8]
    canonical.add_weighted_edges_from([
        ("left", "center", values[0]),
        ("center", "right", values[1]),
        ("right", "tail", values[2]),
    ])
    _assert_spectral_eigenpair(graph, oracle, canonical, weight, True)


@pytest.mark.parametrize("route", ["fnx", "networkx"])
@pytest.mark.parametrize("graph_class", ["Graph", "MultiGraph"])
@pytest.mark.parametrize("weight, expected", [(-3, 6.0), (0, 0.0)])
def test_spectral_preprocessing_two_node_boundary(route, graph_class, weight, expected):
    oracle = getattr(nx, graph_class)()
    oracle.add_edge("first", "second", weight=weight)
    if graph_class == "MultiGraph":
        oracle.add_edge("first", "second", weight=-weight)
        expected *= 2
    graph = oracle.copy() if route == "networkx" else getattr(fnx, graph_class)(oracle)
    assert fnx.algebraic_connectivity(graph) == pytest.approx(expected)
    if weight == 0:
        with pytest.raises(fnx.NetworkXError, match="graph is not connected"):
            fnx.fiedler_vector(graph)
    else:
        assert fnx.fiedler_vector(graph).tolist() == [1.0, -1.0]
        assert fnx.algebraic_connectivity(graph, normalized=True) == pytest.approx(2.0)
