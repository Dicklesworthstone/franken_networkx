"""``franken_networkx.linalg`` routes to fnx's native builders.

``from networkx.linalg import *`` used to bind networkx's matrix/spectral
builders into the ``franken_networkx.linalg`` namespace, so
``fnx.linalg.adjacency_matrix`` silently resolved to networkx's
implementation rather than fnx's native one. These assertions are
object-identity checks (independent of the native extension build), pinning
that the namespace exposes the fnx version.

br-r37-c1-f8j44
"""

from __future__ import annotations

import pytest
import networkx as nx
import franken_networkx as fnx
from franken_networkx import linalg as fnx_linalg

_NATIVE_NAMES = [
    "adjacency_matrix",
    "adjacency_spectrum",
    "algebraic_connectivity",
    "attr_matrix",
    "attr_sparse_matrix",
    "bethe_hessian_matrix",
    "bethe_hessian_spectrum",
    "directed_combinatorial_laplacian_matrix",
    "directed_laplacian_matrix",
    "directed_modularity_matrix",
    "fiedler_vector",
    "incidence_matrix",
    "laplacian_matrix",
    "laplacian_spectrum",
    "modularity_matrix",
    "modularity_spectrum",
    "normalized_laplacian_matrix",
    "normalized_laplacian_spectrum",
    "spectral_bisection",
    "spectral_ordering",
]


@pytest.mark.parametrize("name", _NATIVE_NAMES)
def test_linalg_namespace_exposes_fnx_native(name):
    if not hasattr(fnx, name):
        pytest.skip(f"fnx has no top-level {name}")
    namespaced = getattr(fnx_linalg, name)
    # The namespace must expose fnx's function, not networkx's.
    assert namespaced is getattr(fnx, name)
    if hasattr(nx, name):
        assert namespaced is not getattr(nx, name)


@pytest.mark.parametrize("cls", ["Graph", "DiGraph"])
@pytest.mark.parametrize(
    "kwargs",
    [
        {"normalized": True},
        {"normalized": True, "edge_attr": "weight"},
        {"normalized": True, "rc_order": [9, 0, 1, 2]},
        {"normalized": True, "node_attr": "c"},
    ],
    ids=["plain", "weight", "rc_order", "node_attr"],
)
def test_attr_matrix_normalized_row_without_edges_is_nan_like_networkx(cls, kwargs):
    # br-r37-c1-6zlfk: nx divides each row by its sum in place, so a node with
    # no edges gives a NaN row (0/0); fnx replaced a zero sum with 1.
    import warnings

    import numpy as np

    def matrix(lib):
        g = getattr(lib, cls)()
        g.add_nodes_from((i, {"c": i % 2}) for i in (0, 1, 2, 9))
        g.add_weighted_edges_from([(0, 1, 1.5), (1, 2, 2.0), (2, 0, 1.0), (2, 2, 0.5)])
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            return lib.attr_matrix(g, **kwargs)

    got, expected = matrix(fnx), matrix(nx)
    if isinstance(expected, tuple):
        assert list(got[1]) == list(expected[1])
        got, expected = got[0], expected[0]
    assert np.array_equal(np.asarray(got), np.asarray(expected), equal_nan=True)


# br-r37-c1-64xcg: attr_sparse_matrix is networkx's lil_array (a coo_array once
# normalized), and networkx normalizes it with an in-place multiply that scales
# stored entries only - a row without edges stays 0, where the dense
# attr_matrix gives 0/0 NaN. fnx wrapped the dense answer in a csr_array (so the
# row came out NaN after 6zlfk). Both functions raise networkx's KeyError for a
# missing node attribute or an edge endpoint missing from rc_order - fnx
# skipped those pairs.
def _attr_graphs():
    def sink(L):
        g = L.DiGraph([(0, 1), (1, 2), (0, 2)])
        g.add_node(3)
        return g

    def colored(L):
        g = L.Graph([(0, 1), (1, 2), (2, 3)])
        for node, color in zip(range(4), "rbrg"):
            g.nodes[node]["c"] = color
        return g

    return {
        "digraph_sink": sink,
        "graph_isolated": lambda L: L.Graph([(0, 1), (2, 2)]),
        "multigraph_w": lambda L: L.MultiGraph([(0, 1, {"w": 2}), (0, 1, {"w": 3}), (1, 2, {"w": 1})]),
        "path": lambda L: L.Graph([(0, 1), (1, 2), (2, 3)]),
        "colored": colored,
    }


@pytest.mark.parametrize("name", ["attr_matrix", "attr_sparse_matrix"])
@pytest.mark.parametrize("graph", list(_attr_graphs()))
@pytest.mark.parametrize(
    "kwargs",
    [{}, {"normalized": True}, {"rc_order": [0, 1, 2]}, {"normalized": True, "rc_order": [2, 1, 0]},
     {"edge_attr": "w"}, {"dtype": int}, {"node_attr": "c"}, {"node_attr": "c", "rc_order": ["r", "b"]},
     {"node_attr": "c", "rc_order": ["r", "b", "g"], "normalized": True}],
    ids=["default", "normalized", "rc_order_partial", "normalized_rc", "edge_attr", "dtype_int",
         "node_attr", "node_attr_partial", "node_attr_normalized"],
)
def test_attr_matrices_match_networkx(name, graph, kwargs):
    import warnings

    import numpy as np

    build = _attr_graphs()[graph]

    def outcome(lib):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            try:
                result = getattr(lib, name)(build(lib), **kwargs)
            except Exception as exc:  # noqa: BLE001 - the exception is the outcome
                return type(exc).__name__, str(exc)
        matrix, ordering = (result, None) if "rc_order" in kwargs else result
        dense = matrix.toarray() if hasattr(matrix, "toarray") else matrix
        return type(matrix).__name__, str(dense.dtype), np.nan_to_num(dense, nan=-1.0).tolist(), ordering

    assert outcome(fnx) == outcome(nx)


@pytest.mark.parametrize("namespace", ["top_level", "linalg"])
@pytest.mark.parametrize("weighted", [False, True])
@pytest.mark.parametrize("r", [None, 1.25])
@pytest.mark.parametrize(
    "nodelist",
    [None, [1, 2], [0, 1, 2], [2, 0, 1], [5], [5, 1]],
    ids=["all", "leaves", "subset", "reordered", "isolate", "isolate_and_leaf"],
)
def test_bethe_hessian_subset_uses_whole_graph_regularizer(
    namespace, weighted, r, nodelist
):
    import numpy as np

    results = []
    for lib in (fnx, nx):
        graph = lib.Graph()
        graph.add_nodes_from(range(6))
        if weighted:
            graph.add_weighted_edges_from(
                [(0, 1, 0.5), (0, 2, 2.0), (0, 3, 3.5), (0, 4, 4.0)]
            )
        else:
            graph.add_edges_from((0, leaf) for leaf in range(1, 5))
        api = lib if namespace == "top_level" else lib.linalg
        results.append(api.bethe_hessian_matrix(graph, r=r, nodelist=nodelist))

    actual, expected = results
    assert type(actual) is type(expected)
    assert actual.format == expected.format == "csr"
    np.testing.assert_array_equal(actual.toarray(), expected.toarray())

    if r is None and nodelist == [1, 2]:
        # The full graph has degrees [4, 1, 1, 1, 1, 0], so r=1.5.
        # The selected leaves have no induced edges: H=(r*r-1)*I.
        np.testing.assert_array_equal(actual.toarray(), 1.25 * np.eye(2))


@pytest.mark.parametrize("namespace", ["top_level", "linalg"])
@pytest.mark.parametrize(
    ("nodes", "edges", "nodelist", "r"),
    [
        ([], [], None, None),
        ([0], [], None, None),
        ([0], [], [], None),
        ([0], [], [99], None),
        ([], [], [], 1.25),
        ([0], [], [], 1.25),
        ([0, 1], [(0, 1)], [], None),
        ([0, 1], [(0, 1)], [99], None),
        ([0, 1], [(0, 1)], [0, 0], None),
    ],
    ids=[
        "empty_default",
        "edgeless_default",
        "edgeless_before_empty_nodelist",
        "edgeless_before_missing_node",
        "empty_explicit",
        "edgeless_explicit",
        "empty_nodelist",
        "missing_node",
        "duplicate_node",
    ],
)
def test_bethe_hessian_validation_order_matches_networkx(
    namespace, nodes, edges, nodelist, r
):
    outcomes = []
    for lib in (fnx, nx):
        graph = lib.Graph()
        graph.add_nodes_from(nodes)
        graph.add_edges_from(edges)
        api = lib if namespace == "top_level" else lib.linalg
        try:
            api.bethe_hessian_matrix(graph, r=r, nodelist=nodelist)
        except Exception as exc:
            outcomes.append((type(exc).__name__, str(exc)))
        else:
            pytest.fail("invalid Bethe Hessian input must raise")
    assert outcomes[0] == outcomes[1]


@pytest.mark.parametrize("namespace", ["top_level", "linalg"])
@pytest.mark.parametrize(
    ("kind", "r"),
    [
        ("connected", None),
        ("connected", 1.25),
        ("edgeless", None),
        ("empty", 1.25),
    ],
)
def test_bethe_hessian_unsized_nodelist_is_not_consumed(namespace, kind, r):
    outcomes = []
    for lib in (fnx, nx):
        graph = lib.Graph()
        if kind != "empty":
            graph.add_nodes_from([0, 1])
        if kind == "connected":
            graph.add_edge(0, 1)
        nodelist = iter([0, 1])
        api = lib if namespace == "top_level" else lib.linalg
        try:
            api.bethe_hessian_matrix(graph, r=r, nodelist=nodelist)
        except Exception as exc:
            outcomes.append((type(exc).__name__, str(exc)))
        else:
            pytest.fail("an unsized nodelist must not produce a matrix")
        assert list(nodelist) == [0, 1]
    assert outcomes[0] == outcomes[1]


# Unit attribute matrices count topology even when edge dictionaries contain
# keys that look internal. No user attribute name is reserved as a sentinel.
_UNIT_MATRIX_ATTRIBUTE = "\x00__fnx_attr_matrix_unit__"


def _unit_attribute_graph(lib, graph_type):
    graph = getattr(lib, graph_type)()
    graph.add_nodes_from([0, 1, 2, 3])
    graph.add_edges_from([
        (0, 1, {_UNIT_MATRIX_ATTRIBUTE: 7.0, "weight": 19, None: 23}),
        (1, 2, {_UNIT_MATRIX_ATTRIBUTE: -2.0, "weight": 29, None: 31}),
        (2, 2, {_UNIT_MATRIX_ATTRIBUTE: 0.25, "weight": 37, None: 41}),
    ])
    if graph.is_multigraph():
        graph.add_edge(0, 1, **{_UNIT_MATRIX_ATTRIBUTE: 13, "weight": 43})
    return graph


def _assert_attribute_matrix_equal(actual, expected):
    import numpy as np

    if isinstance(expected, tuple):
        assert actual[1] == expected[1]
        actual, expected = actual[0], expected[0]
    assert actual.dtype == expected.dtype
    np.testing.assert_array_equal(actual, expected)


@pytest.mark.parametrize("graph_type", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("namespace", ["top_level", "linalg"])
@pytest.mark.parametrize(
    "rc_order",
    [None, [3, 2, 0, 1], [2, 0, 1], [0, 1, 0, 2, 3]],
    ids=["default", "reordered", "omit_isolate", "duplicate"],
)
@pytest.mark.parametrize(
    ("dtype", "normalized"),
    [(None, False), ("int64", False), ("float32", False), (None, True)],
)
def test_unit_attr_matrix_ignores_all_edge_attribute_keys(
    graph_type, namespace, rc_order, dtype, normalized
):
    import numpy as np

    options = dict(
        edge_attr=None, rc_order=rc_order, dtype=dtype, normalized=normalized
    )
    function = getattr(fnx if namespace == "top_level" else fnx_linalg, "attr_matrix")
    with np.errstate(invalid="ignore", divide="ignore"):
        expected = nx.attr_matrix(_unit_attribute_graph(nx, graph_type), **options)
        actual = function(_unit_attribute_graph(fnx, graph_type), **options)
    _assert_attribute_matrix_equal(actual, expected)


@pytest.mark.parametrize("graph_type", ["Graph", "DiGraph"])
@pytest.mark.parametrize("value", [0, -7, float("inf"), float("nan"), "not a weight"])
def test_unit_attr_matrix_ignores_mutated_escaped_attributes(graph_type, value):
    import numpy as np

    graphs = [
        _unit_attribute_graph(lib, graph_type)
        for lib in (fnx, nx)
    ]
    for lib, graph in zip((fnx, nx), graphs):
        # Materialize a matrix first, then bypass ordinary dict write hooks.
        # Unit matrices must remain independent of those values and any cache.
        lib.attr_matrix(graph, rc_order=[0, 1, 2, 3])
        attrs = graph[0][1]
        dict.__setitem__(attrs, _UNIT_MATRIX_ATTRIBUTE, value)
        dict.__setitem__(attrs, "weight", value)
        dict.__setitem__(attrs, None, value)
    np.testing.assert_array_equal(
        fnx.attr_matrix(graphs[0], rc_order=[0, 1, 2, 3]),
        nx.attr_matrix(graphs[1], rc_order=[0, 1, 2, 3]),
    )


@pytest.mark.parametrize("graph_type", ["Graph", "DiGraph"])
@pytest.mark.parametrize("edge_attr", ["weight", _UNIT_MATRIX_ATTRIBUTE])
def test_explicit_attr_matrix_selector_still_uses_edge_values(graph_type, edge_attr):
    import numpy as np

    graph = _unit_attribute_graph(fnx, graph_type)
    expected_graph = _unit_attribute_graph(nx, graph_type)
    np.testing.assert_array_equal(
        fnx.attr_matrix(graph, edge_attr=edge_attr, rc_order=[2, 0, 1, 3]),
        nx.attr_matrix(expected_graph, edge_attr=edge_attr, rc_order=[2, 0, 1, 3]),
    )


@pytest.mark.parametrize("graph_type", ["Graph", "DiGraph"])
def test_unit_attr_matrix_falls_back_without_topology_exporter(monkeypatch, graph_type):
    import numpy as np

    monkeypatch.setattr(fnx, "_native_adjacency_index_arrays", None)
    graph = _unit_attribute_graph(fnx, graph_type)
    expected_graph = _unit_attribute_graph(nx, graph_type)
    np.testing.assert_array_equal(
        fnx.attr_matrix(graph, rc_order=[0, 1, 2, 3]),
        nx.attr_matrix(expected_graph, rc_order=[0, 1, 2, 3]),
    )
