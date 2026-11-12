"""Parity coverage for add_weighted_edges_from(**attr).

Bead franken_networkx-m2o1: all four graph-family classes accept
trailing **attr kwargs that apply to every inserted edge, matching
upstream NetworkX.
"""

import networkx as nx
import pytest

import franken_networkx as fnx


@pytest.mark.parametrize(
    ("fnx_ctor", "nx_ctor"),
    [
        (fnx.Graph, nx.Graph),
        (fnx.DiGraph, nx.DiGraph),
        (fnx.MultiGraph, nx.MultiGraph),
        (fnx.MultiDiGraph, nx.MultiDiGraph),
    ],
)
def test_add_weighted_edges_from_applies_extra_attrs(fnx_ctor, nx_ctor):
    fg = fnx_ctor()
    fg.add_weighted_edges_from([(0, 1, 5), (1, 2, 7)], color="red", tag="A")
    ng = nx_ctor()
    ng.add_weighted_edges_from([(0, 1, 5), (1, 2, 7)], color="red", tag="A")

    f_attrs = {(u, v): dict(a) for u, v, a in fg.edges(data=True)}
    n_attrs = {(u, v): dict(a) for u, v, a in ng.edges(data=True)}
    assert f_attrs == n_attrs


@pytest.mark.parametrize(
    "fnx_ctor",
    [fnx.Graph, fnx.DiGraph, fnx.MultiGraph, fnx.MultiDiGraph],
)
def test_add_weighted_edges_from_without_extra_attrs_still_works(fnx_ctor):
    """No-attr call path must still route to the fast Rust method."""
    fg = fnx_ctor()
    fg.add_weighted_edges_from([(0, 1, 5)])
    # Edge attrs contain only the weight.
    edges = list(fg.edges(data=True))
    assert len(edges) == 1
    _, _, attrs = edges[0]
    assert dict(attrs) == {"weight": 5}


@pytest.mark.parametrize(
    ("fnx_ctor", "nx_ctor"),
    [
        (fnx.Graph, nx.Graph),
        (fnx.DiGraph, nx.DiGraph),
    ],
)
def test_add_weighted_edges_from_custom_weight_kwarg_parity(fnx_ctor, nx_ctor):
    """`weight` kwarg selects the attribute name for the scalar."""
    fg = fnx_ctor()
    fg.add_weighted_edges_from([(0, 1, 5)], weight="cost", note="via")
    ng = nx_ctor()
    ng.add_weighted_edges_from([(0, 1, 5)], weight="cost", note="via")
    assert dict(fg[0][1]) == dict(ng[0][1])
