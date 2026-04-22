"""Parity coverage for EdgeView.data() helper across graph families.

Bead franken_networkx-y5u6: G.edges exposes .data() matching upstream
EdgeView.data() contract for Graph, DiGraph, MultiGraph, MultiDiGraph.
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
def test_edges_data_default_matches_networkx(fnx_ctor, nx_ctor):
    fg = fnx_ctor()
    fg.add_edge("a", "b", weight=3)
    fg.add_edge("b", "c")
    ng = nx_ctor()
    ng.add_edge("a", "b", weight=3)
    ng.add_edge("b", "c")
    # data() with no args → (u, v, attrs) tuples
    assert list(fg.edges.data()) == list(ng.edges.data())


@pytest.mark.parametrize(
    ("fnx_ctor", "nx_ctor"),
    [
        (fnx.Graph, nx.Graph),
        (fnx.DiGraph, nx.DiGraph),
        (fnx.MultiGraph, nx.MultiGraph),
        (fnx.MultiDiGraph, nx.MultiDiGraph),
    ],
)
def test_edges_data_attr_name_matches_networkx(fnx_ctor, nx_ctor):
    fg = fnx_ctor()
    fg.add_edge("a", "b", weight=3)
    fg.add_edge("b", "c")
    ng = nx_ctor()
    ng.add_edge("a", "b", weight=3)
    ng.add_edge("b", "c")
    # data('weight') → (u, v, attrs['weight']) with None for missing
    assert list(fg.edges.data("weight")) == list(ng.edges.data("weight"))


@pytest.mark.parametrize(
    ("fnx_ctor", "nx_ctor"),
    [
        (fnx.Graph, nx.Graph),
        (fnx.DiGraph, nx.DiGraph),
        (fnx.MultiGraph, nx.MultiGraph),
        (fnx.MultiDiGraph, nx.MultiDiGraph),
    ],
)
def test_edges_data_attr_name_with_default_matches_networkx(fnx_ctor, nx_ctor):
    fg = fnx_ctor()
    fg.add_edge("a", "b")
    fg.add_edge("b", "c")
    ng = nx_ctor()
    ng.add_edge("a", "b")
    ng.add_edge("b", "c")
    # data('missing', default=X) → (u, v, X) for every edge
    assert list(fg.edges.data("missing", default="NA")) == list(
        ng.edges.data("missing", default="NA")
    )
