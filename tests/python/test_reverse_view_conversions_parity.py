"""Parity coverage for reverse_view conversions (to_directed/to_undirected/reverse).

Bead franken_networkx-lfxu: reverse_view must expose to_directed(),
to_undirected(), and reverse(copy=...) matching upstream's surface.
"""

import networkx as nx
import pytest

import franken_networkx as fnx


@pytest.mark.parametrize(
    ("fnx_ctor", "nx_ctor"),
    [
        (fnx.DiGraph, nx.DiGraph),
        (fnx.MultiDiGraph, nx.MultiDiGraph),
    ],
)
def test_reverse_view_to_directed_matches_networkx(fnx_ctor, nx_ctor):
    fg = fnx_ctor()
    fg.add_edges_from([(1, 2), (2, 3)])
    ng = nx_ctor()
    ng.add_edges_from([(1, 2), (2, 3)])

    frv = fnx.reverse_view(fg)
    nrv = nx.reverse_view(ng)

    fd = frv.to_directed()
    nd = nrv.to_directed()
    # Materialised DiGraph / MultiDiGraph with the reversed edge set.
    assert fd.is_directed()
    assert not fd.is_multigraph() if not fg.is_multigraph() else fd.is_multigraph()
    assert sorted(fd.edges()) == sorted(nd.edges())


@pytest.mark.parametrize(
    ("fnx_ctor", "nx_ctor"),
    [
        (fnx.DiGraph, nx.DiGraph),
        (fnx.MultiDiGraph, nx.MultiDiGraph),
    ],
)
def test_reverse_view_to_undirected_matches_networkx(fnx_ctor, nx_ctor):
    fg = fnx_ctor()
    fg.add_edges_from([(1, 2), (2, 3)])
    ng = nx_ctor()
    ng.add_edges_from([(1, 2), (2, 3)])

    frv = fnx.reverse_view(fg)
    nrv = nx.reverse_view(ng)

    fu = frv.to_undirected()
    nu = nrv.to_undirected()
    assert not fu.is_directed()
    # Undirected edge set comparison (frozenset normalisation).
    assert sorted(sorted(e) for e in fu.edges()) == sorted(
        sorted(e) for e in nu.edges()
    )


@pytest.mark.parametrize(
    ("fnx_ctor", "nx_ctor"),
    [
        (fnx.DiGraph, nx.DiGraph),
        (fnx.MultiDiGraph, nx.MultiDiGraph),
    ],
)
def test_reverse_view_reverse_copy_true_returns_original_orientation(
    fnx_ctor, nx_ctor
):
    fg = fnx_ctor()
    fg.add_edges_from([(1, 2), (2, 3)])
    ng = nx_ctor()
    ng.add_edges_from([(1, 2), (2, 3)])

    frv = fnx.reverse_view(fg)
    nrv = nx.reverse_view(ng)

    fr = frv.reverse(copy=True)
    nr = nrv.reverse(copy=True)

    # Same edge set as the original graph — reverse of a reverse is a
    # copy of the original.
    assert sorted(fr.edges()) == sorted(fg.edges()) == sorted(nr.edges())
    # It's a fresh copy, not the same object.
    assert fr is not fg


@pytest.mark.parametrize(
    ("fnx_ctor", "nx_ctor"),
    [
        (fnx.DiGraph, nx.DiGraph),
        (fnx.MultiDiGraph, nx.MultiDiGraph),
    ],
)
def test_reverse_view_reverse_copy_false_returns_underlying_graph(
    fnx_ctor, nx_ctor
):
    fg = fnx_ctor()
    fg.add_edges_from([(1, 2), (2, 3)])

    frv = fnx.reverse_view(fg)
    fr = frv.reverse(copy=False)
    # reverse(copy=False) on a reverse-view returns the original
    # directed orientation as a live view — matches upstream.
    assert fr is fg
