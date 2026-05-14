"""br-r37-c1-oa0fs: regression — fnx.from_scipy_sparse_array accepts
``edge_attribute=None`` and uses ``None`` as the literal edge-attribute
dict key (matching nx).

Before this fix, fnx raised ``TypeError("argument 'weight': 'None' is
not an instance of 'str'")`` because the PyO3-bound
``add_weighted_edges_from`` (and ``add_edges_from``) require a string
attr key. The Python wrapper now adds each edge first and sets the
``None`` key directly on ``G[u][v]`` (the per-edge dict accepts
arbitrary hashable keys).
"""

from __future__ import annotations

import pytest

import franken_networkx as fnx

try:
    import networkx as nx
    import scipy.sparse as ssp
    import numpy as np

    HAS_DEPS = True
except ImportError:
    HAS_DEPS = False


needs_deps = pytest.mark.skipif(not HAS_DEPS, reason="networkx/scipy/numpy not installed")


@needs_deps
def test_from_scipy_sparse_array_none_attr_undirected():
    m = ssp.csr_matrix([[0, 5], [5, 0]])
    fg = fnx.from_scipy_sparse_array(m, edge_attribute=None)
    ng = nx.from_scipy_sparse_array(m, edge_attribute=None)
    assert list(fg.edges(data=True)) == list(ng.edges(data=True))
    assert list(fg.edges(data=True))[0][2] == {None: 5}


@needs_deps
def test_from_scipy_sparse_array_none_attr_digraph():
    m = ssp.csr_matrix([[0, 5, 0], [0, 0, 3], [0, 0, 0]])
    fg = fnx.from_scipy_sparse_array(m, edge_attribute=None, create_using=fnx.DiGraph)
    ng = nx.from_scipy_sparse_array(m, edge_attribute=None, create_using=nx.DiGraph)
    assert list(fg.edges(data=True)) == list(ng.edges(data=True))


@needs_deps
def test_from_scipy_sparse_array_none_attr_multigraph_parallel():
    m = ssp.csr_matrix(np.array([[0, 2], [2, 0]]))
    fg = fnx.from_scipy_sparse_array(
        m, edge_attribute=None, parallel_edges=True, create_using=fnx.MultiGraph
    )
    ng = nx.from_scipy_sparse_array(
        m, edge_attribute=None, parallel_edges=True, create_using=nx.MultiGraph
    )
    assert sorted(fg.edges(keys=True, data=True)) == sorted(
        ng.edges(keys=True, data=True)
    )


@needs_deps
def test_from_scipy_sparse_array_default_weight_no_regression():
    """Default edge_attribute='weight' path must keep working."""
    m = ssp.csr_matrix([[0, 5], [5, 0]])
    fg = fnx.from_scipy_sparse_array(m)
    ng = nx.from_scipy_sparse_array(m)
    assert list(fg.edges(data=True)) == list(ng.edges(data=True))


@needs_deps
def test_from_scipy_sparse_array_custom_string_attr_no_regression():
    """Custom string edge_attribute path must keep working."""
    m = ssp.csr_matrix([[0, 7], [7, 0]])
    fg = fnx.from_scipy_sparse_array(m, edge_attribute="capacity")
    ng = nx.from_scipy_sparse_array(m, edge_attribute="capacity")
    assert list(fg.edges(data=True)) == list(ng.edges(data=True))
