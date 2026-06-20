"""Parity coverage for DiGraph.reverse(copy=...) / MultiDiGraph.reverse(copy=...).

Bead franken_networkx-b7fx: both directed graph classes must accept
the ``copy`` keyword matching upstream — copy=True materialises a
fresh reversed DiGraph, copy=False returns a frozen live reverse_view.
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
def test_reverse_copy_true_matches_networkx(fnx_ctor, nx_ctor):
    fg = fnx_ctor()
    fg.add_edges_from([(1, 2), (2, 3)])
    ng = nx_ctor()
    ng.add_edges_from([(1, 2), (2, 3)])

    fr = fg.reverse(copy=True)
    nr = ng.reverse(copy=True)

    assert sorted(fr.edges()) == sorted(nr.edges())
    # copy=True produces a materialised (mutable) graph.
    assert not fnx.is_frozen(fr)
    assert not nx.is_frozen(nr)


@pytest.mark.parametrize(
    ("fnx_ctor", "nx_ctor"),
    [
        (fnx.DiGraph, nx.DiGraph),
        (fnx.MultiDiGraph, nx.MultiDiGraph),
    ],
)
def test_reverse_copy_false_returns_frozen_view(fnx_ctor, nx_ctor):
    fg = fnx_ctor()
    fg.add_edges_from([(1, 2), (2, 3)])
    ng = nx_ctor()
    ng.add_edges_from([(1, 2), (2, 3)])

    fr = fg.reverse(copy=False)
    nr = ng.reverse(copy=False)

    assert sorted(fr.edges()) == sorted(nr.edges())
    # copy=False produces a frozen live view.
    assert fnx.is_frozen(fr)
    assert nx.is_frozen(nr)
    assert isinstance(fr, fnx_ctor)
    assert isinstance(nr, nx_ctor)


@pytest.mark.parametrize(
    ("fnx_ctor", "nx_ctor"),
    [
        (fnx.DiGraph, nx.DiGraph),
        (fnx.MultiDiGraph, nx.MultiDiGraph),
    ],
)
def test_global_reverse_copy_false_returns_typed_frozen_view(fnx_ctor, nx_ctor):
    fg = fnx_ctor()
    fg.add_edges_from([(1, 2), (2, 3)])
    ng = nx_ctor()
    ng.add_edges_from([(1, 2), (2, 3)])

    fr = fnx.reverse(fg, copy=False)
    nr = nx.reverse(ng, copy=False)

    assert sorted(fr.edges()) == sorted(nr.edges())
    assert fnx.is_frozen(fr)
    assert nx.is_frozen(nr)
    assert isinstance(fr, fnx_ctor)
    assert isinstance(nr, nx_ctor)


@pytest.mark.parametrize(
    "fnx_ctor",
    [fnx.DiGraph, fnx.MultiDiGraph],
)
def test_reverse_default_is_copy(fnx_ctor):
    """No-arg reverse() defaults to copy=True."""
    fg = fnx_ctor()
    fg.add_edges_from([(1, 2), (2, 3)])
    r = fg.reverse()
    assert not fnx.is_frozen(r)
    assert sorted(r.edges()) == [(2, 1), (3, 2)]


def test_multidigraph_reverse_copy_preserves_keys_attrs_and_row_order():
    fg = fnx.MultiDiGraph()
    ng = nx.MultiDiGraph()
    edges = [
        ("a", "b", "k1", {"weight": 1}),
        ("c", "b", "k2", {"weight": 2}),
        ("a", "b", "k3", {"weight": 3}),
        ("b", "a", "k4", {"weight": 4}),
    ]
    fg.add_edges_from(edges)
    ng.add_edges_from(edges)
    fg["a"]["b"]["k1"]["weight"] = 11
    ng["a"]["b"]["k1"]["weight"] = 11

    fr = fg.reverse(copy=True)
    nr = ng.reverse(copy=True)

    assert list(fr.edges(keys=True, data="weight")) == list(
        nr.edges(keys=True, data="weight")
    )
    assert {
        node: {
            "succ": list(fr.succ[node]),
            "pred": list(fr.pred[node]),
        }
        for node in fr
    } == {
        node: {
            "succ": list(nr.succ[node]),
            "pred": list(nr.pred[node]),
        }
        for node in nr
    }
    fr["b"]["a"]["k1"]["weight"] = 101
    assert fg["a"]["b"]["k1"]["weight"] == 11
