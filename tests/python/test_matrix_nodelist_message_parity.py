"""Parity for matrix exporters' bad-nodelist error wording.

networkx is intentionally *inconsistent* here, and fnx must match each
exporter exactly:

* the sparse / Laplacian exporters (``adjacency_matrix``,
  ``to_scipy_sparse_array``, ``laplacian_matrix``,
  ``normalized_laplacian_matrix``) report the FIRST missing node in
  nodelist order, singular: ``Node {n} in nodelist is not in G``;
* the dense exporters (``to_numpy_array``, ``to_pandas_adjacency``)
  report the whole missing *set*: ``Nodes {set} in nodelist is not in G``.
* ``incidence_matrix`` accepts extra nodelist entries that are not in G, but
  rejects edgelists whose endpoints are absent from the supplied nodelist.

fnx previously emitted the plural set form everywhere. br-r37-c1-6cdtz
"""

from __future__ import annotations

import pytest
import networkx as nx
import franken_networkx as fnx

_SINGULAR = [
    "adjacency_matrix",
    "to_scipy_sparse_array",
    "laplacian_matrix",
    "normalized_laplacian_matrix",
]
_PLURAL = ["to_numpy_array", "to_pandas_adjacency"]


def _graphs():
    return fnx.Graph([(0, 1), (1, 2)]), nx.Graph([(0, 1), (1, 2)])


@pytest.mark.parametrize("fn", _SINGULAR + _PLURAL)
@pytest.mark.parametrize("nodelist", [[0, 1, 99], [0, 1, 99, 98], [98, 99, 0]])
def test_bad_nodelist_message_matches_networkx(fn, nodelist):
    fg, ng = _graphs()
    with pytest.raises(nx.NetworkXError) as fnx_exc:
        getattr(fnx, fn)(fg, nodelist=nodelist)
    with pytest.raises(nx.NetworkXError) as nx_exc:
        getattr(nx, fn)(ng, nodelist=nodelist)
    assert str(fnx_exc.value) == str(nx_exc.value)


@pytest.mark.parametrize("fn", _SINGULAR)
def test_sparse_exporters_report_first_missing_singular(fn):
    fg, _ = _graphs()
    with pytest.raises(nx.NetworkXError) as exc:
        getattr(fnx, fn)(fg, nodelist=[0, 99, 98])
    # First missing in nodelist order, singular, no set braces.
    assert str(exc.value) == "Node 99 in nodelist is not in G"


@pytest.mark.parametrize("fn", _PLURAL)
def test_dense_exporters_report_missing_set_plural(fn):
    fg, _ = _graphs()
    with pytest.raises(nx.NetworkXError) as exc:
        getattr(fnx, fn)(fg, nodelist=[0, 99])
    assert str(exc.value) == "Nodes {99} in nodelist is not in G"


@pytest.mark.parametrize("nodelist", [[0, 1, 2, 99], [99, 0, 1, 2]])
def test_incidence_matrix_accepts_extra_nodelist_nodes_like_networkx(nodelist):
    import numpy as np

    fg, ng = _graphs()

    assert np.array_equal(
        fnx.incidence_matrix(fg, nodelist=nodelist).toarray(),
        nx.incidence_matrix(ng, nodelist=nodelist).toarray(),
    )


@pytest.mark.parametrize("nodelist", [[0, 99], [2, 99, 0]])
def test_incidence_matrix_missing_endpoint_message_matches_networkx(nodelist):
    fg, ng = _graphs()

    with pytest.raises(nx.NetworkXError) as fnx_exc:
        fnx.incidence_matrix(fg, nodelist=nodelist)
    with pytest.raises(nx.NetworkXError) as nx_exc:
        nx.incidence_matrix(ng, nodelist=nodelist)

    assert str(fnx_exc.value) == str(nx_exc.value)


def test_valid_nodelist_unaffected():
    import numpy as np
    fg, ng = _graphs()
    assert np.array_equal(
        fnx.to_numpy_array(fg, nodelist=[2, 0, 1]),
        nx.to_numpy_array(ng, nodelist=[2, 0, 1]),
    )
