"""Parity coverage for edge_subgraph returning frozen views.

Bead franken_networkx-u0bk: edge_subgraph must return a frozen view
across all four graph-family classes matching upstream NetworkX.
"""

import networkx as nx
import pytest

import franken_networkx as fnx


@pytest.mark.parametrize(
    ("fnx_ctor", "nx_ctor"),
    [
        (fnx.Graph, nx.Graph),
        (fnx.DiGraph, nx.DiGraph),
    ],
)
def test_simple_edge_subgraph_is_frozen(fnx_ctor, nx_ctor):
    fg = fnx_ctor()
    fg.add_edges_from([(0, 1), (1, 2), (2, 3)])
    ng = nx_ctor()
    ng.add_edges_from([(0, 1), (1, 2), (2, 3)])

    fh = fg.edge_subgraph([(0, 1), (1, 2)])
    nh = ng.edge_subgraph([(0, 1), (1, 2)])

    assert fnx.is_frozen(fh)
    assert nx.is_frozen(nh)
    with pytest.raises(fnx.NetworkXError):
        fh.add_node(99)


@pytest.mark.parametrize(
    ("fnx_ctor", "nx_ctor"),
    [
        (fnx.MultiGraph, nx.MultiGraph),
        (fnx.MultiDiGraph, nx.MultiDiGraph),
    ],
)
def test_multi_edge_subgraph_is_frozen(fnx_ctor, nx_ctor):
    fg = fnx_ctor()
    fg.add_edge("a", "b", key="k1")
    fg.add_edge("b", "c", key="k2")
    ng = nx_ctor()
    ng.add_edge("a", "b", key="k1")
    ng.add_edge("b", "c", key="k2")

    fh = fg.edge_subgraph([("a", "b", "k1")])
    nh = ng.edge_subgraph([("a", "b", "k1")])

    assert fnx.is_frozen(fh)
    assert nx.is_frozen(nh)
    with pytest.raises(fnx.NetworkXError):
        fh.add_node(99)
