"""Parity coverage for to_directed(as_view=True) in_edges/out_edges.

Bead franken_networkx-qoz2: to_directed live views must expose
in_edges() and out_edges() matching networkx on both Graph and
MultiGraph inputs, including data= kwarg.
"""

import networkx as nx
import pytest

import franken_networkx as fnx


@pytest.mark.parametrize(
    ("fnx_ctor", "nx_ctor"),
    [
        (fnx.Graph, nx.Graph),
        (fnx.MultiGraph, nx.MultiGraph),
    ],
)
def test_to_directed_view_has_in_and_out_edges(fnx_ctor, nx_ctor):
    fg = fnx_ctor()
    fg.add_edges_from([(0, 1), (1, 2)])
    ng = nx_ctor()
    ng.add_edges_from([(0, 1), (1, 2)])

    fv = fg.to_directed(as_view=True)
    nv = ng.to_directed(as_view=True)

    assert hasattr(fv, "in_edges")
    assert hasattr(fv, "out_edges")

    # Same edge set (ordering may differ on either side, so compare sorted).
    assert sorted(fv.in_edges()) == sorted(nv.in_edges())
    assert sorted(fv.out_edges()) == sorted(nv.out_edges())


@pytest.mark.parametrize(
    ("fnx_ctor", "nx_ctor"),
    [
        (fnx.Graph, nx.Graph),
        (fnx.MultiGraph, nx.MultiGraph),
    ],
)
def test_to_directed_view_in_edges_with_data_kwarg(fnx_ctor, nx_ctor):
    fg = fnx_ctor()
    fg.add_edge(0, 1, weight=3)
    ng = nx_ctor()
    ng.add_edge(0, 1, weight=3)

    fv = fg.to_directed(as_view=True)
    nv = ng.to_directed(as_view=True)

    f_rows = sorted(fv.in_edges(data=True), key=lambda r: (r[0], r[1]))
    n_rows = sorted(nv.in_edges(data=True), key=lambda r: (r[0], r[1]))
    assert f_rows == n_rows


@pytest.mark.parametrize(
    ("fnx_ctor", "nx_ctor"),
    [
        (fnx.Graph, nx.Graph),
        (fnx.MultiGraph, nx.MultiGraph),
    ],
)
def test_to_directed_view_nbunch_argument(fnx_ctor, nx_ctor):
    """in_edges / out_edges accept an nbunch filter."""
    fg = fnx_ctor()
    fg.add_edges_from([(0, 1), (1, 2), (2, 3)])
    ng = nx_ctor()
    ng.add_edges_from([(0, 1), (1, 2), (2, 3)])

    fv = fg.to_directed(as_view=True)
    nv = ng.to_directed(as_view=True)

    assert sorted(fv.in_edges([2])) == sorted(nv.in_edges([2]))
    assert sorted(fv.out_edges([2])) == sorted(nv.out_edges([2]))
