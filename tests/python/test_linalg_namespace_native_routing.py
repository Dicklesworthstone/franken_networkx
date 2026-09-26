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
