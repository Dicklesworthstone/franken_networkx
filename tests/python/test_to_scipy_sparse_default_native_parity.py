"""Default sparse-export native route parity for br-r37-c1-04z53.1."""

from __future__ import annotations

import numpy as np
import pytest

import franken_networkx as fnx

try:
    import networkx as nx

    HAS_NX = True
except ImportError:
    HAS_NX = False

needs_nx = pytest.mark.skipif(not HAS_NX, reason="networkx not installed")


def _csr_sig(A):
    A = A.tocsr()
    A.sort_indices()
    return (
        A.shape,
        A.dtype.str,
        A.indptr.tobytes(),
        A.indices.tobytes(),
        np.ascontiguousarray(A.data).tobytes(),
    )


def test_default_missing_weight_attr_routes_to_native_unweighted(monkeypatch):
    graph = fnx.Graph()
    graph.add_edges_from([(0, 1), (1, 2)])
    calls = []

    def fake_native(actual_graph, nodelist, weight, default_weight):
        calls.append((actual_graph, tuple(nodelist), weight, default_weight))
        return [0, 1, 1, 2], [1, 0, 2, 1], [1.0, 1.0, 1.0, 1.0]

    monkeypatch.setattr(fnx, "_native_adjacency_arrays", fake_native)

    matrix = fnx.to_scipy_sparse_array(graph)

    assert calls == [(graph, (0, 1, 2), None, 1.0)]
    assert matrix.dtype == np.dtype("int64")
    assert matrix.toarray().tolist() == [[0, 1, 0], [1, 0, 1], [0, 1, 0]]


@needs_nx
def test_default_weight_attr_keeps_dtype_inference_fallback(monkeypatch):
    nx_graph = nx.Graph()
    fnx_graph = fnx.Graph()
    for u, v, weight in [(0, 1, 2), (1, 2, 3.5)]:
        nx_graph.add_edge(u, v, weight=weight)
        fnx_graph.add_edge(u, v, weight=weight)

    def fail_native(*_args):
        raise AssertionError("weighted dtype=None path must stay on fallback")

    monkeypatch.setattr(fnx, "_native_adjacency_arrays", fail_native)

    expected = nx.to_scipy_sparse_array(nx_graph)
    actual = fnx.to_scipy_sparse_array(fnx_graph)

    assert _csr_sig(actual) == _csr_sig(expected)
    assert actual.dtype == expected.dtype


@needs_nx
@pytest.mark.parametrize("directed", [False, True])
def test_default_missing_weight_attr_matches_networkx(directed):
    nx_graph = nx.DiGraph() if directed else nx.Graph()
    fnx_graph = fnx.DiGraph() if directed else fnx.Graph()
    edges = [(0, 1), (1, 2), (2, 0), (2, 3), (3, 3)]
    nx_graph.add_edges_from(edges)
    fnx_graph.add_edges_from(edges)

    assert _csr_sig(fnx.to_scipy_sparse_array(fnx_graph)) == _csr_sig(
        nx.to_scipy_sparse_array(nx_graph)
    )
    assert _csr_sig(fnx.adjacency_matrix(fnx_graph)) == _csr_sig(
        nx.adjacency_matrix(nx_graph)
    )
    assert _csr_sig(fnx.laplacian_matrix(fnx_graph)) == _csr_sig(
        nx.laplacian_matrix(nx_graph)
    )
