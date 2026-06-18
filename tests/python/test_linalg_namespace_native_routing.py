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
