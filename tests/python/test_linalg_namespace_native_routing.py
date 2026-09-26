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
