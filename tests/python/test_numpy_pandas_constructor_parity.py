"""Parity for Graph constructor with numpy.ndarray / pandas.DataFrame.

Bead br-r37-c1-rxigp. ``fnx.Graph(numpy_adj_matrix)`` and
``fnx.Graph(pandas_df)`` returned empty graphs (every edge silently
dropped). nx auto-detects these types via ``to_networkx_graph`` and
dispatches to ``from_numpy_array`` / ``from_pandas_adjacency``. Both
helpers exist on fnx but the constructor wasn't routing to them.
"""

from __future__ import annotations

import pytest

import franken_networkx as fnx

try:
    import networkx as nx
    HAS_NX = True
except ImportError:
    HAS_NX = False

try:
    import numpy as np
    HAS_NP = True
except ImportError:
    HAS_NP = False

try:
    import pandas as pd
    HAS_PD = True
except ImportError:
    HAS_PD = False

needs_nx = pytest.mark.skipif(not HAS_NX, reason="networkx not installed")
needs_np = pytest.mark.skipif(not HAS_NP, reason="numpy not installed")
needs_pd = pytest.mark.skipif(not HAS_PD, reason="pandas not installed")


# ---------------------------------------------------------------------------
# numpy.ndarray adjacency matrix
# ---------------------------------------------------------------------------

@needs_nx
@needs_np
def test_graph_from_numpy_path_adjacency():
    A = np.array([[0, 1, 0], [1, 0, 1], [0, 1, 0]])
    f = fnx.Graph(A)
    n = nx.Graph(A)
    assert sorted(f.edges) == sorted(n.edges) == [(0, 1), (1, 2)]


@needs_nx
@needs_np
def test_digraph_from_numpy_directed_adjacency():
    A = np.array([[0, 1, 0], [0, 0, 1], [0, 0, 0]])
    f = fnx.DiGraph(A)
    n = nx.DiGraph(A)
    assert sorted(f.edges) == sorted(n.edges) == [(0, 1), (1, 2)]


@needs_nx
@needs_np
def test_graph_from_numpy_with_weights():
    A = np.array([[0, 2.5, 0], [2.5, 0, 1.0], [0, 1.0, 0]])
    f = fnx.Graph(A)
    n = nx.Graph(A)
    assert dict(f[0]) == dict(n[0])
    assert dict(f[1]) == dict(n[1])


@needs_nx
@needs_np
def test_multigraph_from_numpy_with_parallel_edges():
    """An adjacency value > 1 means parallel edges in nx for MultiGraph."""
    A = np.array([[0, 2, 0], [2, 0, 1], [0, 1, 0]])
    f = fnx.MultiGraph(A)
    n = nx.MultiGraph(A)
    assert f.number_of_edges() == n.number_of_edges()


@needs_nx
@needs_np
def test_empty_numpy_array_yields_empty_graph():
    A = np.zeros((3, 3), dtype=int)
    f = fnx.Graph(A)
    n = nx.Graph(A)
    assert sorted(f.edges) == sorted(n.edges) == []
    assert sorted(f.nodes) == sorted(n.nodes) == [0, 1, 2]


# ---------------------------------------------------------------------------
# pandas.DataFrame adjacency
# ---------------------------------------------------------------------------

@needs_nx
@needs_pd
def test_graph_from_pandas_dataframe_adjacency():
    df = pd.DataFrame([[0, 1, 0], [1, 0, 1], [0, 1, 0]])
    f = fnx.Graph(df)
    n = nx.Graph(df)
    assert sorted(f.edges) == sorted(n.edges) == [(0, 1), (1, 2)]


@needs_nx
@needs_pd
def test_digraph_from_pandas_dataframe_adjacency():
    df = pd.DataFrame([[0, 1, 0], [0, 0, 1], [0, 0, 0]])
    f = fnx.DiGraph(df)
    n = nx.DiGraph(df)
    assert sorted(f.edges) == sorted(n.edges)


@needs_nx
@needs_pd
def test_pandas_with_string_index_node_labels():
    """Nodes should be the dataframe row/column labels."""
    df = pd.DataFrame(
        [[0, 1, 0], [1, 0, 1], [0, 1, 0]],
        index=["a", "b", "c"],
        columns=["a", "b", "c"],
    )
    f = fnx.Graph(df)
    n = nx.Graph(df)
    assert sorted(f.nodes) == sorted(n.nodes) == ["a", "b", "c"]
    assert sorted(f.edges) == sorted(n.edges)


# ---------------------------------------------------------------------------
# Regression check — list-of-edges constructor still works
# ---------------------------------------------------------------------------

@needs_nx
def test_list_of_edges_constructor_still_works():
    """The numpy/pandas detection must not regress the edge-list path."""
    f = fnx.Graph([(0, 1), (1, 2), (2, 3)])
    n = nx.Graph([(0, 1), (1, 2), (2, 3)])
    assert sorted(f.edges) == sorted(n.edges)


@needs_nx
def test_dict_of_dict_constructor_still_works():
    """Earlier br-r37-c1-9m2vs / br-r37-c1-lc3em paths must still work."""
    f = fnx.Graph({0: {1: {"w": 5}}})
    n = nx.Graph({0: {1: {"w": 5}}})
    assert list(f.edges(data=True)) == list(n.edges(data=True))


def _matrix_import_snapshot(graph):
    return (
        list(graph.nodes(data=True)),
        list(graph.edges(data=True)),
        list(graph.degree(weight="weight")),
        dict(graph.graph),
    )


def _matrix_import(lib, route, matrix, graph):
    if route == "generic":
        return lib.to_networkx_graph(matrix, create_using=graph)
    if route.startswith("scipy"):
        from scipy import sparse

        matrix = sparse.csr_array(matrix)
        module = lib.convert_matrix if route.endswith("module") else lib
        return module.from_scipy_sparse_array(matrix, create_using=graph)
    module = lib.convert_matrix if route.endswith("module") else lib
    return module.from_numpy_array(matrix, create_using=graph)


@needs_nx
@needs_np
@pytest.mark.parametrize("graph_type", ["Graph", "DiGraph"])
@pytest.mark.parametrize("storage", ["nodes", "adjacency", "both"])
@pytest.mark.parametrize("route", ["numpy", "scipy", "numpy_module", "scipy_module", "generic"])
def test_matrix_import_populates_supplied_storage(graph_type, storage, route):
    pytest.importorskip("scipy")
    matrix = np.array([[0, 2, 0, 0], [5, 7, 3, 0], [0, 0, 0, 0], [0, 0, 0, 0]])
    results = []
    for lib in (nx, fnx):
        graph = getattr(lib, graph_type)()
        assigned = {}
        if storage in ("nodes", "both"):
            assigned["_node"] = {}
        if storage in ("adjacency", "both"):
            assigned["_adj"] = {}
            if graph.is_directed():
                assigned["_pred"] = {}
        for name, mapping in assigned.items():
            setattr(graph, name, mapping)
        graph.add_edge("old", "data", weight=99)
        graph.graph["old"] = True
        result = _matrix_import(lib, route, matrix, graph)
        assert result is graph
        for name, mapping in assigned.items():
            assert getattr(graph, name) is mapping
        results.append(_matrix_import_snapshot(result))
        assert set(result) == set(range(4))
        assert result[1][1]["weight"] == 7
        if graph.is_directed():
            assert result._succ[0][1] is result._pred[1][0]
        else:
            assert result._adj[0][1] is result._adj[1][0]
    assert results[0] == results[1]


@needs_nx
@needs_np
@pytest.mark.parametrize("graph_type", ["Graph", "DiGraph"])
@pytest.mark.parametrize("route", ["numpy", "scipy"])
def test_matrix_import_runs_public_bulk_mutation_hooks(graph_type, route):
    pytest.importorskip("scipy")
    results = []
    for lib in (nx, fnx):
        graph = getattr(lib, graph_type)()
        original_nodes = graph.add_nodes_from
        original_edges = graph.add_edges_from
        events = []

        def add_nodes(nodes):
            nodes = tuple(nodes)
            events.append(("nodes", nodes))
            original_nodes(nodes)

        def add_edges(edges, **attrs):
            rows = list(edges)
            events.append(("edges", len(rows)))
            original_edges(
                ((u, v, {**data, "imported": True}) for u, v, data in rows),
                **attrs,
            )

        graph.add_nodes_from = add_nodes
        graph.add_edges_from = add_edges
        result = _matrix_import(lib, route, np.array([[0, 2], [0, 0]]), graph)
        assert result is graph
        results.append((events, _matrix_import_snapshot(result)))
    assert results[0] == results[1]
    assert results[1][0] == [("nodes", ()), ("nodes", (0, 1)), ("edges", 1)]


@needs_nx
@needs_np
@pytest.mark.parametrize("graph_type", ["Graph", "DiGraph"])
def test_sparse_import_preserves_weighted_hook_and_partial_failure(graph_type):
    sparse = pytest.importorskip("scipy.sparse")
    results = []
    for lib in (nx, fnx):
        graph = getattr(lib, graph_type)()
        original = graph.add_weighted_edges_from

        def add_weighted(edges, **options):
            original([next(iter(edges))], **options)
            raise RuntimeError("weighted insertion stopped")

        graph.add_weighted_edges_from = add_weighted
        matrix = sparse.csr_array(np.array([[0, 2, 0], [0, 0, 3], [0, 0, 0]]))
        with pytest.raises(RuntimeError, match="weighted insertion stopped"):
            lib.from_scipy_sparse_array(matrix, create_using=graph)
        results.append(_matrix_import_snapshot(graph))
    assert results[0] == results[1]
    assert results[1][0] == [(0, {}), (1, {}), (2, {})]
    assert results[1][1] == [(0, 1, {"weight": 2})]


@needs_nx
@needs_np
@pytest.mark.parametrize("graph_type", ["Graph", "DiGraph"])
def test_numpy_provider_observes_inserted_nodes(graph_type):
    results = []
    for lib in (nx, fnx):
        graph = getattr(lib, graph_type)()
        observations = []

        class ArrayProvider(np.ndarray):
            def nonzero(self):
                observations.append(tuple(graph))
                self[0, 2] = len(graph) + 10
                return super().nonzero()

        matrix = np.array([[0, 2, 0], [0, 0, 3], [0, 0, 0]]).view(ArrayProvider)
        result = lib.from_numpy_array(matrix, create_using=graph)
        results.append((observations, _matrix_import_snapshot(result)))
    assert results[0] == results[1]
    assert results[1][0] == [(0, 1, 2)]
    assert (0, 2, {"weight": 13}) in results[1][1][1]


@needs_nx
@needs_np
@pytest.mark.parametrize("graph_type", ["Graph", "DiGraph"])
def test_sparse_provider_observes_inserted_nodes(graph_type):
    sparse = pytest.importorskip("scipy.sparse")
    results = []
    for lib in (nx, fnx):
        graph = getattr(lib, graph_type)()
        observations = []

        class SparseProvider:
            __slots__ = ()
            shape = (3, 3)
            dtype = np.dtype("int64")
            format = "coo"

            def tocoo(self):
                observations.append(tuple(graph))
                return sparse.coo_array(
                    ([len(graph) + 10], ([0], [2])), shape=self.shape
                )

        result = lib.from_scipy_sparse_array(SparseProvider(), create_using=graph)
        results.append((observations, _matrix_import_snapshot(result)))
    assert results[0] == results[1]
    assert results[1][0] == [(0, 1, 2)]
    assert results[1][1][1] == [(0, 2, {"weight": 13})]


@needs_nx
@needs_np
@pytest.mark.parametrize("format", ["csr", "csc"])
@pytest.mark.parametrize("graph_type", ["Graph", "DiGraph"])
def test_compressed_sparse_import_does_not_require_coo_conversion(format, graph_type):
    sparse = pytest.importorskip("scipy.sparse")

    class CompressedProvider(getattr(sparse, format + "_array")):
        def tocoo(self, *args, **kwargs):
            raise RuntimeError("COO conversion is not available")

    matrix = CompressedProvider(np.array([[0, 2, 0], [5, 7, 3], [0, 0, 0]]))
    expected = nx.from_scipy_sparse_array(matrix, create_using=getattr(nx, graph_type))
    actual = fnx.from_scipy_sparse_array(matrix, create_using=getattr(fnx, graph_type))
    assert _matrix_import_snapshot(actual) == _matrix_import_snapshot(expected)


@needs_nx
@needs_np
@pytest.mark.parametrize("format", ["csr", "csc"])
@pytest.mark.parametrize("changed", ["indices", "indptr", "data"])
def test_compressed_sparse_import_snapshots_before_weighted_hook(format, changed):
    sparse = pytest.importorskip("scipy.sparse")
    results = []
    for lib in (nx, fnx):
        graph = lib.DiGraph()
        matrix = sparse.coo_array(([2], ([0], [1])), shape=(3, 3)).asformat(format)
        original = graph.add_weighted_edges_from

        def add_weighted(edges, **options):
            if changed == "indices":
                matrix.indices[0] = 2
            elif changed == "indptr":
                matrix.indptr[:] = [0, 0, 0, 1]
            else:
                matrix.data[0] = 99
            return original(edges, **options)

        graph.add_weighted_edges_from = add_weighted
        result = lib.from_scipy_sparse_array(matrix, create_using=graph)
        results.append(_matrix_import_snapshot(result))
    assert results[0] == results[1]
    assert results[1][1] == [(0, 1, {"weight": 2})]


@needs_nx
@needs_np
@pytest.mark.parametrize("graph_type", ["Graph", "DiGraph"])
def test_dictionary_sparse_provider_is_consumed_by_weighted_hook(graph_type):
    pytest.importorskip("scipy")
    results = []
    for lib in (nx, fnx):
        graph = getattr(lib, graph_type)()
        original = graph.add_weighted_edges_from

        def add_weighted(edges, **options):
            graph.graph["hook_seen"] = True
            return original(edges, **options)

        class DictionaryProvider:
            shape = (3, 3)
            dtype = np.dtype("int64")
            format = "dok"

            def items(self):
                weight = 13 if graph.graph.get("hook_seen") else 2
                return [((0, 2), np.int64(weight))]

        graph.add_weighted_edges_from = add_weighted
        result = lib.from_scipy_sparse_array(DictionaryProvider(), create_using=graph)
        results.append(_matrix_import_snapshot(result))
    assert results[0] == results[1]
    assert results[1][1] == [(0, 2, {"weight": 13})]


@needs_nx
@needs_np
@pytest.mark.parametrize("graph_type", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("format", ["coo", "csr", "csc", "dok", "lil", "bsr"])
def test_sparse_storage_order_and_parallel_edges_remain_correct(graph_type, format):
    sparse = pytest.importorskip("scipy.sparse")
    matrix = sparse.coo_array(
        ([2, 3, 1, 4], ([1, 0, 1, 2], [0, 2, 1, 2])), shape=(4, 4)
    ).asformat(format)
    expected = nx.from_scipy_sparse_array(
        matrix, parallel_edges=True, create_using=getattr(nx, graph_type)
    )
    actual = fnx.from_scipy_sparse_array(
        matrix, parallel_edges=True, create_using=getattr(fnx, graph_type)
    )
    assert _matrix_import_snapshot(actual) == _matrix_import_snapshot(expected)
