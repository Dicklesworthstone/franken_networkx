"""to_numpy_array hands edge values to numpy exactly as networkx does.

br-r37-c1-rc0923-epic-silent-wrong-answers-nro4w.6. The native COO builders
return float64 and substituted the unit default for any weight that is not a
real number, whatever dtype the caller asked for: a complex weight came out as
1+0j, a big int lost precision under dtype=object, structured dtypes read
(1, 1), and a non-numeric weight gave 1.0 where networkx raises (or, for None,
gives nan). networkx builds the array with numpy advanced-index assignment of
the attribute values, so numpy decides every conversion and error.
"""

from __future__ import annotations

import networkx as nx
import numpy as np
import pytest

import franken_networkx as fnx

CLASSES = ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"]
WEIGHTS = {
    "int": 3,
    "float": 2.5,
    "bool": True,
    "complex": 1 + 2j,
    "big_int": 922337203685477580102,
    "none": None,
    "numeric_str": "3.5",
    "str": "abc",
    "list": [1, 2],
    "nan": float("nan"),
}
DTYPES = {"default": None, "float": float, "int": int, "complex": complex, "object": object}


def _outcome(module, cls, weight_value, dtype, weight="weight"):
    G = getattr(module, cls)()
    G.add_edge(0, 1, weight=weight_value)
    G.add_edge(1, 2)  # no weight attribute: networkx's default is 1.0
    G.add_node(3)
    try:
        A = module.to_numpy_array(G, dtype=dtype, weight=weight)
    except Exception as exc:  # compared by type only; numpy owns the message
        return ("raised", type(exc).__name__)
    return ("ok", str(A.dtype), repr(A.tolist()))


@pytest.mark.filterwarnings("ignore")
@pytest.mark.parametrize("cls", CLASSES)
@pytest.mark.parametrize("dtype", sorted(DTYPES))
@pytest.mark.parametrize("value", sorted(WEIGHTS))
def test_weight_value_and_dtype_parity(cls, dtype, value):
    want = _outcome(nx, cls, WEIGHTS[value], DTYPES[dtype])
    got = _outcome(fnx, cls, WEIGHTS[value], DTYPES[dtype])
    assert got == want


@pytest.mark.parametrize("cls", ["Graph", "DiGraph"])
def test_structured_dtype_reads_each_field_like_networkx(cls):
    dtype = np.dtype([("weight", int), ("cost", float)])
    graphs = []
    for module in (nx, fnx):
        G = getattr(module, cls)()
        G.add_edge(0, 1, weight=10)
        G.add_edge(1, 2, cost=5)
        G.add_edge(2, 3, weight=3, cost=-4.0)
        graphs.append(module.to_numpy_array(G, dtype=dtype, weight=None))
    want, got = graphs
    assert got.dtype == want.dtype
    for field in dtype.names:
        np.testing.assert_array_equal(got[field], want[field])


@pytest.mark.parametrize("cls", CLASSES)
def test_structured_dtype_errors_match_networkx(cls):
    dtype = np.dtype([("weight", int), ("cost", int)])
    for weight in ("weight", None):
        outcomes = []
        for module in (nx, fnx):
            G = getattr(module, cls)()
            G.add_edge(0, 1, weight=1, cost=2)
            try:
                A = module.to_numpy_array(G, dtype=dtype, weight=weight)
                outcomes.append(("ok", repr(A.tolist())))
            except Exception as exc:
                outcomes.append(("raised", type(exc).__name__, str(exc)))
        assert outcomes[1] == outcomes[0], (cls, weight)


def test_edgeless_structured_request_returns_the_filled_array_like_networkx():
    dtype = np.dtype([("weight", int), ("cost", int)])
    for module in (nx, fnx):
        G = module.Graph()
        G.add_nodes_from([0, 1])
        A = module.to_numpy_array(G, dtype=dtype, weight="weight")  # no error: no edges
        assert A.shape == (2, 2)


def test_float_weights_still_take_the_native_path(monkeypatch):
    """The fail-closed change must not push the common case off the fast path."""
    import franken_networkx as package

    calls = []
    real = package._native_adjacency_arrays

    def counting(*args, **kwargs):
        calls.append(1)
        return real(*args, **kwargs)

    monkeypatch.setattr(package, "_native_adjacency_arrays", counting)
    G = fnx.Graph()
    G.add_weighted_edges_from([(0, 1, 2.0), (1, 2, 3.5)])
    A = fnx.to_numpy_array(G)
    assert calls and A[0, 1] == 2.0


@pytest.mark.parametrize("cls", CLASSES)
@pytest.mark.parametrize(
    "value,nonedge", [(2**53 + 1, 0), (2**63 + 1, np.uint64(0))]
)
def test_inferred_integer_dtype_keeps_exact_edge_values(cls, value, nonedge):
    matrices = []
    for module in (nx, fnx):
        graph = getattr(module, cls)()
        graph.add_edge("u", "v", weight=value)
        matrices.append(module.to_numpy_array(graph, nonedge=nonedge))
    expected, actual = matrices
    assert actual.dtype == expected.dtype
    np.testing.assert_array_equal(actual, expected)
    assert int(actual[0, 1]) == value


@pytest.mark.parametrize("cls", CLASSES)
@pytest.mark.parametrize("dtype", [np.longdouble, np.clongdouble])
def test_extended_precision_dtype_receives_original_value(cls, dtype):
    if np.finfo(np.longdouble).nmant <= np.finfo(np.float64).nmant:
        pytest.skip("platform longdouble has no additional integer precision")
    value = 2**53 + 1
    if dtype is np.clongdouble:
        # NumPy converts a Python int through double for a complex dtype;
        # an extended real scalar preserves its precision in that conversion.
        value = np.longdouble(value)
    matrices = []
    for module in (nx, fnx):
        graph = getattr(module, cls)()
        graph.add_edge("u", "v", weight=value)
        matrices.append(module.to_numpy_array(graph, dtype=dtype))
    expected, actual = matrices
    assert actual.dtype == expected.dtype
    np.testing.assert_array_equal(actual, expected)
    assert int(actual[0, 1].real) == 2**53 + 1


@pytest.mark.parametrize("cls", ["Graph", "DiGraph"])
def test_float32_conversion_rounds_original_integer_once(cls):
    # Just above a float32 midpoint, but below the resolution of float64.
    value = 2**60 + 2**36 + 1
    matrices = []
    for module in (nx, fnx):
        graph = getattr(module, cls)()
        graph.add_edge("u", "v", weight=value)
        matrices.append(module.to_numpy_array(graph, dtype=np.float32))
    np.testing.assert_array_equal(matrices[1], matrices[0])


@pytest.mark.parametrize("cls", ["MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("dtype", [None, np.float16, np.float32, np.float64, complex, object])
@pytest.mark.parametrize(
    "weights",
    [
        [2**53, 1, -(2**53)],
        [1e16, 1.0, -1e16],
        [1e8, 1.0, -1e8],
        [0.1, 0.2, 0.3],
    ],
)
def test_parallel_weights_reduce_before_array_conversion(cls, dtype, weights):
    matrices = []
    for module in (nx, fnx):
        graph = getattr(module, cls)()
        graph.add_nodes_from(["u", "v", "isolated"])
        for value in weights:
            graph.add_edge("u", "v", weight=value)
            graph.add_edge("u", "u", weight=value)
        matrices.append(module.to_numpy_array(graph, dtype=dtype))
    expected, actual = matrices
    assert actual.dtype == expected.dtype
    np.testing.assert_array_equal(actual, expected)


@pytest.mark.parametrize("cls", ["MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("weight", [None, "weight"])
def test_parallel_unit_edge_count_is_cast_only_after_reduction(cls, weight):
    matrices = []
    for module in (nx, fnx):
        graph = getattr(module, cls)()
        graph.add_edges_from((0, 1) for _ in range(2051))
        matrices.append(module.to_numpy_array(graph, dtype=np.float16, weight=weight))
    expected, actual = matrices
    np.testing.assert_array_equal(actual, expected)
    assert actual[0, 1] == np.float16(2051)


@pytest.mark.parametrize("cls", CLASSES)
def test_none_weight_key_uses_live_attribute_values(cls):
    matrices = []
    for module in (nx, fnx):
        graph = getattr(module, cls)()
        graph.add_edges_from([(0, 1, {None: 7, "weight": 100}), (1, 2, {"weight": 200})])
        matrices.append(module.to_numpy_array(graph, weight=None))
    np.testing.assert_array_equal(matrices[1], matrices[0])
    assert matrices[1][0, 1] == 7
    assert matrices[1][1, 2] == 1


@pytest.mark.parametrize("cls", ["MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("reducer", [sum, min, max])
def test_parallel_reduction_preserves_filters_fill_order_and_mutations(cls, reducer):
    graph_pairs = []
    for module in (nx, fnx):
        graph = getattr(module, cls)()
        graph.add_nodes_from(["isolated", "v", "u", "outside"])
        graph.add_edge("u", "v", key="first", weight=2**53)
        graph.add_edge("u", "v", key="second", weight=-(2**53))
        graph.add_edge("u", "u", weight=3)
        graph.add_edge("outside", "v", weight=17)
        graph_pairs.append(graph)
    options = dict(
        nodelist=["u", "v", "isolated"],
        multigraph_weight=reducer,
        nonedge=-7,
        order="F",
    )
    for _ in range(2):
        expected = nx.to_numpy_array(graph_pairs[0], **options)
        actual = fnx.to_numpy_array(graph_pairs[1], **options)
        np.testing.assert_array_equal(actual, expected)
        assert actual.dtype == expected.dtype
        assert actual.flags.f_contiguous
        for graph in graph_pairs:
            graph["u"]["v"]["first"]["weight"] = 2**53 + 1


@pytest.mark.parametrize("cls", ["MultiGraph", "MultiDiGraph"])
def test_numpy_export_namespace_and_backend_preserve_exact_parallel_sum(cls):
    graph = getattr(nx, cls)()
    for value in (2**53, 1, -(2**53)):
        graph.add_edge("u", "v", weight=value)
    expected = nx.to_numpy_array(graph)
    from franken_networkx.backend import BackendInterface

    converted = BackendInterface.convert_from_nx(graph, preserve_all_attrs=True)
    np.testing.assert_array_equal(fnx.convert_matrix.to_numpy_array(converted), expected)
    np.testing.assert_array_equal(
        nx.to_numpy_array(graph, backend="franken_networkx"), expected
    )


# --- to_scipy_sparse_array format keyword (br-r37-c1-rc0923-epic-silent-wrong-answers-nro4w.7)


@pytest.mark.parametrize("fmt", ["csr", "csc", "coo", "bsr", "lil", "dia", "dok", "any_other"])
def test_sparse_format_keyword_matches_networkx(fmt):
    outcomes = []
    for module in (nx, fnx):
        try:
            A = module.to_scipy_sparse_array(module.path_graph(4), format=fmt)
            outcomes.append(("ok", type(A).__name__, A.format, repr(A.todense().tolist())))
        except Exception as exc:
            outcomes.append(("raised", type(exc).__name__, str(exc)))
    assert outcomes[1] == outcomes[0]


def test_backend_result_conversion_keeps_the_sparse_array_type():
    """networkx passes a backend's result through ``convert_to_nx`` (always in
    its backend-test mode, the path networkx's own test_convert_scipy takes).
    scipy's dok_array subclasses dict, and the conversion used to flatten it
    into a plain dict, losing ``.todense()``."""
    from franken_networkx.backend import BackendInterface

    A = BackendInterface.convert_to_nx(fnx.to_scipy_sparse_array(fnx.path_graph(4), format="dok"))
    assert type(A).__name__ == "dok_array"
    np.testing.assert_array_equal(
        A.todense(), nx.to_scipy_sparse_array(nx.path_graph(4), format="dok").todense()
    )


def test_backend_result_conversion_preserves_container_subclasses():
    from collections import OrderedDict, namedtuple

    from franken_networkx.backend import _convert_result_to_nx

    Pair = namedtuple("Pair", "a b")
    for value in (OrderedDict(a=1), Pair(1, 2), {"a": 1}, [1, 2], (1, 2)):
        assert _convert_result_to_nx(value) is value
    converted = _convert_result_to_nx({"g": fnx.path_graph(2)})
    assert type(converted["g"]) is nx.Graph
