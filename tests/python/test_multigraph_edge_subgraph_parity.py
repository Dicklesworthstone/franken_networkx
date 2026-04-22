"""Parity coverage for MultiGraph/MultiDiGraph edge_subgraph(...).adjacency().

Upstream NetworkX yields (node, filtered multigraph adjacency mapping) pairs
from the edge_subgraph's .adjacency(), preserving edge keys and attributes.
FrankenNetworkX must produce the same content in the same node order.
"""

from collections.abc import Mapping

import networkx as nx
import pytest

import franken_networkx as fnx


def _deep_adjacency(it):
    return [
        (node, {k: dict(inner) for k, inner in dict(nbrs).items()})
        for node, nbrs in it
    ]


@pytest.mark.parametrize(
    ("fnx_ctor", "nx_ctor"),
    [
        (fnx.MultiGraph, nx.MultiGraph),
        (fnx.MultiDiGraph, nx.MultiDiGraph),
    ],
)
def test_multigraph_edge_subgraph_adjacency_preserves_mapping_contract(
    fnx_ctor, nx_ctor
):
    fg = fnx_ctor()
    fg.add_edge("a", "b", key="k1", weight=3)
    fg.add_edge("c", "d", key="k2")
    ng = nx_ctor()
    ng.add_edge("a", "b", key="k1", weight=3)
    ng.add_edge("c", "d", key="k2")

    fh = fg.edge_subgraph([("a", "b", "k1")])
    nh = ng.edge_subgraph([("a", "b", "k1")])

    # Each neighbor payload is a Mapping, not a bare list or node key.
    for _, payload in fh.adjacency():
        assert isinstance(payload, Mapping)

    # Deep content and node ordering match upstream.
    assert _deep_adjacency(fh.adjacency()) == _deep_adjacency(nh.adjacency())


@pytest.mark.parametrize(
    ("fnx_ctor", "nx_ctor"),
    [
        (fnx.MultiGraph, nx.MultiGraph),
        (fnx.MultiDiGraph, nx.MultiDiGraph),
    ],
)
def test_multigraph_edge_subgraph_adjacency_item_access_is_readonly(
    fnx_ctor, nx_ctor
):
    fg = fnx_ctor()
    fg.add_edge("a", "b", key="k1", weight=3)
    ng = nx_ctor()
    ng.add_edge("a", "b", key="k1", weight=3)

    fh = fg.edge_subgraph([("a", "b", "k1")])
    nh = ng.edge_subgraph([("a", "b", "k1")])

    # Both H[n] and H.adj[n] must be Mappings that reject __setitem__.
    for accessor in (lambda g, n: g[n], lambda g, n: g.adj[n]):
        fnbrs = accessor(fh, "a")
        nnbrs = accessor(nh, "a")
        assert isinstance(fnbrs, Mapping)
        with pytest.raises(TypeError):
            fnbrs["x"] = {}
        with pytest.raises(TypeError):
            nnbrs["x"] = {}
        # Deep content match: {'b': {'k1': {'weight': 3}}}
        fdeep = {k: dict(v) for k, v in fnbrs.items()}
        ndeep = {k: dict(v) for k, v in nnbrs.items()}
        assert fdeep == ndeep


@pytest.mark.parametrize(
    ("fnx_ctor", "nx_ctor"),
    [
        (fnx.MultiGraph, nx.MultiGraph),
        (fnx.MultiDiGraph, nx.MultiDiGraph),
    ],
)
def test_multigraph_edge_subgraph_adj_mapping_helpers_deep_match(fnx_ctor, nx_ctor):
    fg = fnx_ctor()
    fg.add_edge("a", "b", key="k1", weight=3)
    fg.add_edge("b", "c")
    ng = nx_ctor()
    ng.add_edge("a", "b", key="k1", weight=3)
    ng.add_edge("b", "c")

    fh = fg.edge_subgraph([("a", "b", "k1")])
    nh = ng.edge_subgraph([("a", "b", "k1")])

    for attr in ("items", "keys", "values", "get"):
        assert hasattr(fh.adj, attr)

    def three_level(it):
        return [
            (
                k,
                {
                    kk: {kkk: dict(vvv) for kkk, vvv in dict(vv).items()}
                    for kk, vv in dict(v).items()
                },
            )
            for k, v in it
        ]

    assert three_level(fh.adj.items()) == three_level(nh.adj.items())
    assert list(fh.adj.keys()) == list(nh.adj.keys())


@pytest.mark.parametrize(
    ("fnx_ctor", "nx_ctor"),
    [
        (fnx.MultiGraph, nx.MultiGraph),
        (fnx.MultiDiGraph, nx.MultiDiGraph),
    ],
)
def test_multigraph_edge_subgraph_multi_key_adjacency_preserves_mapping(
    fnx_ctor, nx_ctor
):
    # Same endpoints, two keys — the subgraph must keep only the selected key.
    fg = fnx_ctor()
    fg.add_edge("a", "b", key="k1", weight=3)
    fg.add_edge("a", "b", key="k2", weight=7)
    ng = nx_ctor()
    ng.add_edge("a", "b", key="k1", weight=3)
    ng.add_edge("a", "b", key="k2", weight=7)

    fh = fg.edge_subgraph([("a", "b", "k2")])
    nh = ng.edge_subgraph([("a", "b", "k2")])

    assert _deep_adjacency(fh.adjacency()) == _deep_adjacency(nh.adjacency())
