"""Sparse interchange preserves source values and SciPy's coercion order."""

import networkx as nx
import numpy as np
import pytest

import franken_networkx as fnx

pytest.importorskip("scipy.sparse")

CLASSES = ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"]
FORMATS = ["csr", "csc", "coo", "lil", "dok", "bsr", "dia"]


def _graphs(cls, values, *, weight="weight", self_loop=False):
    graphs = []
    for module in (nx, fnx):
        graph = getattr(module, cls)()
        graph.add_nodes_from(["source", "target", "isolate"])
        target = "source" if self_loop else "target"
        for value in values:
            if graph.is_multigraph():
                key = graph.add_edge("source", target)
                graph["source"][target][key][weight] = value
            else:
                graph.add_edge("source", target)
                graph["source"][target][weight] = value
        graphs.append(graph)
    return graphs


def _assert_sparse_equal(expected, actual):
    assert type(actual) is type(expected)
    assert actual.format == expected.format
    assert actual.dtype == expected.dtype
    assert actual.shape == expected.shape
    np.testing.assert_array_equal(actual.toarray(), expected.toarray())
    if expected.format == "coo":
        np.testing.assert_array_equal(actual.row, expected.row)
        np.testing.assert_array_equal(actual.col, expected.col)
        np.testing.assert_array_equal(actual.data, expected.data)


@pytest.mark.parametrize("cls", CLASSES)
@pytest.mark.parametrize("format", FORMATS)
@pytest.mark.parametrize(
    "value,dtype",
    [(2**53 + 1, np.int64), (2**63 + 1, np.uint64), (2**53 + 1, None), (2**63 + 1, None)],
)
def test_wide_integer_weights_survive_sparse_export(cls, format, value, dtype):
    original, graph = _graphs(cls, [value])
    expected = nx.to_scipy_sparse_array(original, dtype=dtype, format=format)
    actual = fnx.to_scipy_sparse_array(graph, dtype=dtype, format=format)
    _assert_sparse_equal(expected, actual)
    assert int(actual.toarray()[0, 1]) == value


@pytest.mark.parametrize("cls", CLASSES)
@pytest.mark.parametrize("format", ["csr", "coo"])
@pytest.mark.parametrize(
    "value",
    [
        np.int32(5),
        np.uint64(2**63 + 1),
        np.float32(1.25),
        np.longdouble("1.0000000000000000001"),
        np.complex64(2 + 3j),
        np.bool_(True),
    ],
)
def test_default_dtype_inference_preserves_numpy_scalar_types(cls, format, value):
    original, graph = _graphs(cls, [value])
    _assert_sparse_equal(
        nx.to_scipy_sparse_array(original, format=format),
        fnx.to_scipy_sparse_array(graph, format=format),
    )


@pytest.mark.parametrize("cls", ["MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("format", ["csr", "csc", "coo"])
@pytest.mark.parametrize(
    "values,dtype",
    [
        ([2**53 + 1, -(2**53)], None),
        ([127, 2], np.int8),
        ([1.5, 1.5], np.int64),
        ([1e8, 1.0, -1e8], np.float32),
        ([1e16, 1.0, -1e16], None),
        ([2.0, 3.0], None),
        ([2 + 3j, 1 - 7j], np.complex128),
        ([np.longdouble(2**53 + 1), -np.longdouble(2**53)], np.longdouble),
        ([True, False], np.bool_),
    ],
)
def test_parallel_edges_are_cast_before_sparse_reduction(cls, format, values, dtype):
    original, graph = _graphs(cls, values)
    _assert_sparse_equal(
        nx.to_scipy_sparse_array(original, dtype=dtype, format=format),
        fnx.to_scipy_sparse_array(graph, dtype=dtype, format=format),
    )


@pytest.mark.parametrize("cls", ["MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("weight", ["cost", ("cost", 1)])
def test_nondefault_weight_uses_the_same_per_edge_coercion(cls, weight):
    original, graph = _graphs(cls, [1.75, 1.75], weight=weight)
    actual = fnx.to_scipy_sparse_array(graph, weight=weight, dtype=np.int64)
    expected = nx.to_scipy_sparse_array(original, weight=weight, dtype=np.int64)
    _assert_sparse_equal(expected, actual)
    assert actual[0, 1] == 2


@pytest.mark.parametrize("cls", CLASSES)
@pytest.mark.parametrize("format", ["csr", "coo"])
def test_none_weight_key_reads_live_attribute_values(cls, format):
    original, graph = _graphs(cls, [7], weight=None)
    _assert_sparse_equal(
        nx.to_scipy_sparse_array(original, weight=None, format=format),
        fnx.to_scipy_sparse_array(graph, weight=None, format=format),
    )
    assert fnx.to_scipy_sparse_array(graph, weight=None, format=format).toarray()[0, 1] == 7


@pytest.mark.parametrize("cls", ["Graph", "DiGraph"])
@pytest.mark.parametrize("dtype", [np.float32, np.complex64])
def test_narrow_float_conversion_does_not_round_through_float64(cls, dtype):
    original, graph = _graphs(cls, [2**60 + 2**36 + 1])
    _assert_sparse_equal(
        nx.to_scipy_sparse_array(original, dtype=dtype),
        fnx.to_scipy_sparse_array(graph, dtype=dtype),
    )


@pytest.mark.parametrize("cls", CLASSES)
@pytest.mark.parametrize("format", ["csr", "coo"])
@pytest.mark.parametrize("value", [float("inf"), float("nan"), np.finfo(float).max, True])
@pytest.mark.filterwarnings("ignore:overflow encountered")
@pytest.mark.filterwarnings("ignore:invalid value encountered")
def test_self_loop_correction_preserves_numpy_numeric_semantics(cls, format, value):
    original, graph = _graphs(cls, [value], self_loop=True)
    _assert_sparse_equal(
        nx.to_scipy_sparse_array(original, format=format),
        fnx.to_scipy_sparse_array(graph, format=format),
    )


@pytest.mark.parametrize("cls", CLASSES)
@pytest.mark.parametrize("format", ["csr", "coo"])
@pytest.mark.parametrize("value,dtype", [(2 + 3j, float), (2 + 3j, int), ("not-a-number", float)])
def test_invalid_weights_raise_instead_of_becoming_unit_edges(cls, format, value, dtype):
    original, graph = _graphs(cls, [value])
    with pytest.raises((TypeError, ValueError)) as expected:
        nx.to_scipy_sparse_array(original, dtype=dtype, format=format)
    with pytest.raises(type(expected.value)):
        fnx.to_scipy_sparse_array(graph, dtype=dtype, format=format)


@pytest.mark.parametrize("cls", CLASSES)
@pytest.mark.parametrize("dtype", [np.int64, np.longdouble])
def test_reordered_subset_and_view_keep_live_weights(cls, dtype):
    original, graph = _graphs(cls, [2])
    for item in (original, graph):
        if item.is_multigraph():
            item["source"]["target"][0]["weight"] = 2**53 + 1
        else:
            item["source"]["target"]["weight"] = 2**53 + 1
    nodelist = ["target", "source"]
    for expected_graph, actual_graph in (
        (original, graph),
        (original.subgraph(nodelist), graph.subgraph(nodelist)),
    ):
        _assert_sparse_equal(
            nx.to_scipy_sparse_array(expected_graph, nodelist=nodelist, dtype=dtype),
            fnx.to_scipy_sparse_array(actual_graph, nodelist=nodelist, dtype=dtype),
        )


@pytest.mark.parametrize("cls", ["MultiGraph", "MultiDiGraph"])
def test_edgeless_multigraph_infers_float_and_retains_isolates(cls):
    original, graph = _graphs(cls, [])
    _assert_sparse_equal(
        nx.to_scipy_sparse_array(original), fnx.to_scipy_sparse_array(graph)
    )


@pytest.mark.parametrize("cls", ["Graph", "DiGraph"])
def test_integer_sparse_roundtrip_restores_exact_edge_weights(cls):
    _, graph = _graphs(cls, [2**53 + 1])
    matrix = fnx.to_scipy_sparse_array(graph, dtype=np.int64)
    rebuilt = fnx.from_scipy_sparse_array(matrix, create_using=getattr(fnx, cls))
    assert rebuilt[0][1]["weight"] == 2**53 + 1
    assert list(rebuilt) == [0, 1, 2]


@pytest.mark.parametrize("cls", CLASSES)
@pytest.mark.parametrize("format", ["csr", "csc", "coo", "dok"])
@pytest.mark.parametrize(
    "literal,complex_value",
    [
        ("1.0000000000000000001", False),
        ("1e400", False),
        ("1.0000000000000000001", True),
    ],
    ids=["extended-mantissa", "extended-exponent", "extended-complex"],
)
def test_extended_precision_sparse_import_and_roundtrip(cls, format, literal, complex_value):
    if np.finfo(np.longdouble).nmant <= np.finfo(np.float64).nmant:
        pytest.skip("platform has no extended-precision NumPy floating-point type")

    import scipy.sparse

    value = np.longdouble(literal)
    if complex_value:
        value = np.clongdouble(value) * (1 + 1j)
    matrix = scipy.sparse.coo_array(
        ([value, value], ([0, 1], [1, 0])), shape=(3, 3)
    ).asformat(format)
    original = nx.from_scipy_sparse_array(matrix, create_using=getattr(nx, cls))
    graph = fnx.from_scipy_sparse_array(matrix, create_using=getattr(fnx, cls))

    assert list(graph) == list(original) == [0, 1, 2]
    expected = next(iter(original.edges(data="weight")))[2]
    actual = next(iter(graph.edges(data="weight")))[2]
    assert actual == expected
    assert type(actual) is type(expected)
    assert np.isfinite(actual)
    _assert_sparse_equal(
        nx.to_scipy_sparse_array(original, format="csr"),
        fnx.to_scipy_sparse_array(graph, format="csr"),
    )


def _edge_protocol_graph(cls, weight, trace):
    """Make subscription and the later self-loop get observably different."""
    graph = getattr(nx, cls)()
    graph.add_nodes_from(["source", "target", "isolate"])

    class Correction(float):
        def __new__(cls, value, edge):
            result = super().__new__(cls, value)
            result.edge = edge
            return result

        def __neg__(self):
            trace.append(("neg", self.edge))
            return float.__neg__(self)

    class EdgeData(dict):
        def __init__(self, edge, value):
            super().__init__({weight: value})
            self.edge = edge

        def __contains__(self, key):
            trace.append(("contains", self.edge, key))
            return dict.__contains__(self, key)

        def __getitem__(self, key):
            trace.append(("getitem", self.edge, key))
            return dict.__getitem__(self, key)

        def get(self, key, default=None):
            trace.append(("get", self.edge, key))
            return Correction(dict.get(self, key, default) + 0.25, self.edge)

    edges = [
        ("source", "target", 4.0),
        ("source", "source", 2.0),
        ("target", "target", 3.0),
    ]
    if graph.is_multigraph():
        edges.extend([("source", "source", 1.25), ("target", "target", 0.75)])
    for edge_id, (u, v, value) in enumerate(edges):
        if graph.is_multigraph():
            key = graph.add_edge(u, v)
            attrs = EdgeData(edge_id, value)
            graph._adj[u][v][key] = attrs
            if graph.is_directed():
                graph._pred[v][u][key] = attrs
            else:
                graph._adj[v][u][key] = attrs
        else:
            graph.add_edge(u, v)
            attrs = EdgeData(edge_id, value)
            graph._adj[u][v] = attrs
            if graph.is_directed():
                graph._pred[v][u] = attrs
            else:
                graph._adj[v][u] = attrs
    return graph


@pytest.mark.parametrize("cls", CLASSES)
@pytest.mark.parametrize("weight", ["weight", None, ("cost", 0)])
@pytest.mark.parametrize("format", ["csr", "coo"])
def test_sparse_export_preserves_edge_and_selfloop_read_protocol(cls, weight, format):
    expected_trace, actual_trace = [], []
    original = _edge_protocol_graph(cls, weight, expected_trace)
    graph = _edge_protocol_graph(cls, weight, actual_trace)
    expected = nx.to_scipy_sparse_array(original, weight=weight, format=format)
    if format == "coo":
        actual = fnx.to_scipy_sparse_array(graph, weight=weight, format=format)
    else:
        # PageRank uses this owned exporter directly so live providers are not
        # consumed by unrelated graph conversion or native-route probing.
        actual = fnx._sparse_array_from_edge_values(
            graph, {node: i for i, node in enumerate(graph)}, None, weight, format
        )
    _assert_sparse_equal(expected, actual)
    assert actual_trace == expected_trace
    assert any(event[0] == "getitem" for event in actual_trace)
    if graph.is_directed():
        assert not any(event[0] in ("get", "neg") for event in actual_trace)
    else:
        gets = [i for i, event in enumerate(actual_trace) if event[0] == "get"]
        negations = [i for i, event in enumerate(actual_trace) if event[0] == "neg"]
        assert len(gets) == len(negations) == (4 if graph.is_multigraph() else 2)
        assert max(gets) < min(negations)


@pytest.mark.parametrize("cls", CLASSES)
@pytest.mark.parametrize("weight", ["weight", None, ("cost", 0)])
def test_sparse_export_preserves_foreign_edge_provider_arguments(cls, weight):
    def build(trace):
        graph = getattr(nx, cls)()
        graph.add_edge("source", "target")
        if graph.is_multigraph():
            graph["source"]["target"][0][weight] = 7
        else:
            graph["source"]["target"][weight] = 7
        edge_view = graph.edges

        def edges(nbunch=None, data=False, *, default=None):
            trace.append((nbunch, data, default))
            return edge_view(nbunch=nbunch, data=data, default=default)

        graph.edges = edges
        return graph

    expected_trace, actual_trace = [], []
    original, graph = build(expected_trace), build(actual_trace)
    _assert_sparse_equal(
        nx.to_scipy_sparse_array(original, weight=weight, format="coo"),
        fnx.to_scipy_sparse_array(graph, weight=weight, format="coo"),
    )
    assert actual_trace == expected_trace == [(None, weight, 1)]


@pytest.mark.parametrize("cls", CLASSES)
@pytest.mark.parametrize("weight", [True, False, np.bool_(True), np.bool_(False)])
@pytest.mark.parametrize("has_edges", [False, True])
def test_sparse_logical_views_preserve_boolean_selector_identity(cls, weight, has_edges):
    original, graph = _graphs(cls, [7] if has_edges else [], weight=True, self_loop=True)
    for item in (original, graph):
        if has_edges:
            attrs = item["source"]["source"]
            if item.is_multigraph():
                attrs = attrs[0]
            attrs[False] = 11
    original = original.subgraph(list(original))
    graph = graph.subgraph(list(graph))
    try:
        expected = nx.to_scipy_sparse_array(
            original, dtype=float, weight=weight, format="coo"
        )
    except (TypeError, ValueError) as expected_error:
        with pytest.raises(type(expected_error)) as actual_error:
            fnx._sparse_array_from_edge_values(
                graph, {node: i for i, node in enumerate(graph)}, float, weight, "coo"
            )
        assert str(actual_error.value) == str(expected_error)
    else:
        _assert_sparse_equal(
            expected,
            fnx._sparse_array_from_edge_values(
                graph, {node: i for i, node in enumerate(graph)}, float, weight, "coo"
            ),
        )


@pytest.mark.parametrize("cls", CLASSES)
@pytest.mark.parametrize("weight", ["weight", None, ("cost", 0)])
def test_pagerank_preserves_sparse_selfloop_read_protocol(cls, weight, monkeypatch):
    expected_trace, actual_trace = [], []
    original = _edge_protocol_graph(cls, weight, expected_trace)
    graph = _edge_protocol_graph(cls, weight, actual_trace)
    expected = nx.pagerank(original, weight=weight)

    def forbidden(*args, **kwargs):
        raise AssertionError("live PageRank must use its owned solver on the original graph")

    monkeypatch.setattr(fnx, "_coerce_arg_to_fnx_graph", forbidden)
    monkeypatch.setattr(nx, "pagerank", forbidden)
    actual = fnx.pagerank(graph, weight=weight)
    assert actual == expected
    assert actual_trace == expected_trace
