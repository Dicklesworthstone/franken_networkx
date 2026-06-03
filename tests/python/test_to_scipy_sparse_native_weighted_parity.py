"""Byte-level parity for the native weighted to_scipy_sparse_array fast path.

Bead br-r37-c1-wqtfe (perf).

to_scipy_sparse_array now routes a string ``weight`` key through the native
Rust ``adjacency_arrays`` COO builder when ``dtype`` is pinned (the hot matrix
consumers — hits, kemeny, laplacian/spectral — all pass ``dtype=float``),
~7x faster than the per-edge Python boundary loop. The native helper reads the
Rust ``inner`` AttrMap, so the wrapper syncs Python-visible attr mutations first.

These tests pin the produced CSR (shape, dtype, indptr, indices, data) to nx
byte-for-byte, including the post-creation weight-mutation (staleness) case and
the dtype=None path. dtype=None still uses the value-type-preserving Python
fallback when any requested weight attr exists; when the attr is provably absent,
it may use the native unit-weight path.
"""

from __future__ import annotations

import random

import numpy as np
import pytest

import franken_networkx as fnx

try:
    import networkx as nx
    HAS_NX = True
except ImportError:
    HAS_NX = False

needs_nx = pytest.mark.skipif(not HAS_NX, reason="networkx not installed")


def _csr_payload(A):
    A = A.tocsr()
    A.sort_indices()
    return (
        A.shape,
        A.dtype.str,
        A.indptr.tobytes(),
        A.indices.tobytes(),
        np.ascontiguousarray(A.data).tobytes(),
    )


def _assert_csr_payload_equal(left, right):
    np.testing.assert_equal(_csr_payload(left), _csr_payload(right))


def _build(directed, kind, seed):
    rng = random.Random(seed)
    n = rng.randint(1, 30)
    ng = nx.DiGraph() if directed else nx.Graph()
    fg = fnx.DiGraph() if directed else fnx.Graph()
    nodes = list(range(n))
    rng.shuffle(nodes)
    for u in nodes:
        ng.add_node(u)
        fg.add_node(u)
    seen = set()
    for _ in range(rng.randint(0, n * 2)):
        u, v = rng.choice(nodes), rng.choice(nodes)
        if (u, v) in seen:
            continue
        seen.add((u, v))
        if kind == "unweighted" or kind == "mutated":
            ng.add_edge(u, v)
            fg.add_edge(u, v)
        elif kind == "wint":
            w = rng.randint(1, 5)
            ng.add_edge(u, v, weight=w)
            fg.add_edge(u, v, weight=w)
        else:  # wfloat
            w = rng.choice([1.5, 2.0, 3.25])
            ng.add_edge(u, v, weight=w)
            fg.add_edge(u, v, weight=w)
    if kind == "mutated":
        for u, v in list(ng.edges()):
            w = rng.choice([2, 4.5])
            ng[u][v]["weight"] = w
            fg[u][v]["weight"] = w
    return ng, fg


@needs_nx
@pytest.mark.parametrize("directed", [False, True])
@pytest.mark.parametrize("kind", ["unweighted", "wint", "wfloat", "mutated"])
@pytest.mark.parametrize("dtype", [float, None, int])
@pytest.mark.parametrize("weight", ["weight", None])
@pytest.mark.parametrize("seed", list(range(6)))
def test_csr_byte_identical_to_networkx(directed, kind, dtype, weight, seed):
    ng, fg = _build(directed, kind, seed * 101 + 7)
    if len(ng) == 0:
        return
    a = nx.to_scipy_sparse_array(ng, dtype=dtype, weight=weight)
    b = fnx.to_scipy_sparse_array(fg, dtype=dtype, weight=weight)
    _assert_csr_payload_equal(a, b)


@needs_nx
def test_dtype_float_weighted_uses_native_and_matches():
    # explicit dtype=float + string weight -> native path; mutated weights too
    ng, fg = nx.Graph(), fnx.Graph()
    for u, v in [(0, 1), (1, 2), (2, 0), (2, 3)]:
        ng.add_edge(u, v, weight=1.0)
        fg.add_edge(u, v, weight=1.0)
    # mutate post-creation (staleness path)
    ng[0][1]["weight"] = 7.5
    fg[0][1]["weight"] = 7.5
    a = nx.adjacency_matrix(ng, nodelist=list(ng), dtype=float)
    b = fnx.adjacency_matrix(fg, nodelist=list(fg), dtype=float)
    _assert_csr_payload_equal(a, b)


@needs_nx
def test_dtype_float_default_graph_routes_default_order_native(monkeypatch):
    native_default = getattr(fnx, "_native_adjacency_default_order_arrays", None)
    if native_default is None:
        pytest.skip("native sparse helper unavailable")

    graph = fnx.Graph()
    graph.add_edge(0, 1, weight=2.5)
    graph.add_edge(1, 2, weight=3.5)
    calls = []

    def fail_generic(*_args):
        raise AssertionError("default weighted Graph CSR route should use default helper")

    def wrapped_default(actual_graph, weight_attr, default_weight):
        calls.append((actual_graph, weight_attr, default_weight))
        return native_default(actual_graph, weight_attr, default_weight)

    monkeypatch.setattr(fnx, "_native_adjacency_arrays", fail_generic)
    monkeypatch.setattr(fnx, "_native_adjacency_default_order_arrays", wrapped_default)

    matrix = fnx.to_scipy_sparse_array(graph, dtype=float, weight="weight")

    assert calls == [(graph, "weight", 1.0)]
    assert matrix.dtype == np.dtype("float64")
    assert matrix.toarray().tolist() == [
        [0.0, 2.5, 0.0],
        [2.5, 0.0, 3.5],
        [0.0, 3.5, 0.0],
    ]


@needs_nx
def test_dtype_none_absent_string_weight_routes_native(monkeypatch):
    native_adjacency = getattr(fnx, "_native_adjacency_arrays", None)
    native_index = getattr(fnx, "_native_adjacency_index_arrays", None)
    native_default_index = getattr(fnx, "_native_adjacency_default_order_index_arrays", None)
    if native_adjacency is None or native_index is None or native_default_index is None:
        pytest.skip("native sparse helpers unavailable")

    ng, fg = nx.Graph(), fnx.Graph()
    for u, v in [(0, 1), (1, 2), (2, 0), (2, 3)]:
        ng.add_edge(u, v)
        fg.add_edge(u, v)

    calls = []

    def fail_has_attr(_graph, _weight):
        raise AssertionError("absent-weight sparse route should fuse attr scan")

    def wrapped_adjacency(graph, nodelist, weight, default_weight):
        calls.append(("adjacency", weight, default_weight))
        return native_adjacency(graph, nodelist, weight, default_weight)

    def wrapped_index(graph, nodelist, absent_weight_attr):
        calls.append(("index", absent_weight_attr))
        return native_index(graph, nodelist, absent_weight_attr)

    def wrapped_default_index(graph, absent_weight_attr):
        calls.append(("default_index", absent_weight_attr))
        return native_default_index(graph, absent_weight_attr)

    monkeypatch.setattr(fnx, "_native_has_edge_attr", fail_has_attr)
    monkeypatch.setattr(fnx, "_native_adjacency_arrays", wrapped_adjacency)
    monkeypatch.setattr(fnx, "_native_adjacency_index_arrays", wrapped_index)
    monkeypatch.setattr(
        fnx, "_native_adjacency_default_order_index_arrays", wrapped_default_index
    )

    a = nx.to_scipy_sparse_array(ng, dtype=None, weight="weight")
    b = fnx.to_scipy_sparse_array(fg, dtype=None, weight="weight")

    _assert_csr_payload_equal(a, b)
    assert b.dtype.kind in {"i", "u"}
    assert ("default_index", "weight") in calls
    assert not any(call[0] == "adjacency" for call in calls)


@needs_nx
def test_dtype_none_present_string_weight_routes_typed_default_native(monkeypatch):
    native_adjacency = getattr(fnx, "_native_adjacency_arrays", None)
    native_index = getattr(fnx, "_native_adjacency_index_arrays", None)
    native_default_index = getattr(fnx, "_native_adjacency_default_order_index_arrays", None)
    native_typed = getattr(fnx, "_native_adjacency_default_order_typed_arrays", None)
    if (
        native_adjacency is None
        or native_index is None
        or native_default_index is None
        or native_typed is None
    ):
        pytest.skip("native sparse helpers unavailable")

    ng, fg = nx.Graph(), fnx.Graph()
    ng.add_edge(0, 1, weight=2.0)
    fg.add_edge(0, 1, weight=2.0)
    ng.add_edge(1, 2)
    fg.add_edge(1, 2)

    calls = []

    def fail_has_attr(_graph, _weight):
        raise AssertionError("present-weight sparse route should use index probe")

    def wrapped_adjacency(graph, nodelist, weight, default_weight):
        calls.append(("adjacency", weight, default_weight))
        return native_adjacency(graph, nodelist, weight, default_weight)

    def wrapped_index(graph, nodelist, absent_weight_attr):
        calls.append(("index", absent_weight_attr))
        return native_index(graph, nodelist, absent_weight_attr)

    def wrapped_default_index(graph, absent_weight_attr):
        calls.append(("default_index", absent_weight_attr))
        return native_default_index(graph, absent_weight_attr)

    def wrapped_typed(graph, weight_attr, default_weight):
        calls.append(("typed", weight_attr, default_weight))
        return native_typed(graph, weight_attr, default_weight)

    monkeypatch.setattr(fnx, "_native_has_edge_attr", fail_has_attr)
    monkeypatch.setattr(fnx, "_native_adjacency_arrays", wrapped_adjacency)
    monkeypatch.setattr(fnx, "_native_adjacency_index_arrays", wrapped_index)
    monkeypatch.setattr(
        fnx, "_native_adjacency_default_order_index_arrays", wrapped_default_index
    )
    monkeypatch.setattr(fnx, "_native_adjacency_default_order_typed_arrays", wrapped_typed)

    a = nx.to_scipy_sparse_array(ng, dtype=None, weight="weight")
    b = fnx.to_scipy_sparse_array(fg, dtype=None, weight="weight")

    _assert_csr_payload_equal(a, b)
    assert b.dtype.kind == "f"
    assert ("default_index", "weight") in calls
    assert ("typed", "weight", 1.0) in calls
    assert not any(call[0] == "adjacency" for call in calls)


@needs_nx
def test_dtype_none_present_int_string_weight_preserves_int_dtype():
    ng, fg = nx.Graph(), fnx.Graph()
    for graph in (ng, fg):
        graph.add_edge(0, 1, weight=2)
        graph.add_edge(1, 2)
        graph.add_edge(2, 3, weight=5)

    a = nx.to_scipy_sparse_array(ng, dtype=None, weight="weight")
    b = fnx.to_scipy_sparse_array(fg, dtype=None, weight="weight")

    _assert_csr_payload_equal(a, b)
    assert b.dtype.kind in {"i", "u"}


@needs_nx
def test_dtype_none_present_integral_float_string_weight_preserves_float_dtype():
    ng, fg = nx.Graph(), fnx.Graph()
    for graph in (ng, fg):
        graph.add_edge(0, 1, weight=2.0)
        graph.add_edge(1, 2, weight=3.0)

    a = nx.to_scipy_sparse_array(ng, dtype=None, weight="weight")
    b = fnx.to_scipy_sparse_array(fg, dtype=None, weight="weight")

    _assert_csr_payload_equal(a, b)
    assert b.dtype.kind == "f"


@needs_nx
def test_dtype_none_bool_string_weight_keeps_fallback_dtype():
    ng, fg = nx.Graph(), fnx.Graph()
    for graph in (ng, fg):
        graph.add_edge(0, 1, weight=True)
        graph.add_edge(1, 2, weight=False)

    a = nx.to_scipy_sparse_array(ng, dtype=None, weight="weight")
    b = fnx.to_scipy_sparse_array(fg, dtype=None, weight="weight")

    _assert_csr_payload_equal(a, b)
    assert b.dtype == a.dtype


@needs_nx
def test_hits_matches_networkx():
    # end-to-end consumer of the fast path
    ng, fg = nx.Graph(), fnx.Graph()
    for u, v in [(0, 1), (1, 2), (2, 3), (3, 0), (0, 2), (1, 3), (2, 4)]:
        ng.add_edge(u, v)
        fg.add_edge(u, v)
    nh, na = nx.hits(ng)
    fh, fa = fnx.hits(fg)
    for k in nh:
        assert fh[k] == pytest.approx(nh[k], abs=1e-9)
        assert fa[k] == pytest.approx(na[k], abs=1e-9)
