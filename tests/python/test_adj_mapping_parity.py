"""Parity coverage for Graph/DiGraph/MultiGraph/MultiDiGraph `.adj` mapping helpers.

Upstream NetworkX exposes `items()`, `keys()`, `values()`, and `get()` on every
`<Graph>.adj` view. FrankenNetworkX must match that contract.
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
def test_adj_exposes_mapping_helpers(fnx_ctor, nx_ctor):
    fg = fnx_ctor()
    fg.add_edges_from([(1, 2, {"w": 3}), (2, 3, {"w": 5}), (3, 4)])
    ng = nx_ctor()
    ng.add_edges_from([(1, 2, {"w": 3}), (2, 3, {"w": 5}), (3, 4)])

    for attr in ("items", "keys", "values", "get"):
        assert hasattr(fg.adj, attr), f"{fnx_ctor.__name__}.adj is missing {attr}"

    assert list(fg.adj.keys()) == list(ng.adj.keys())
    assert [(k, dict(v)) for k, v in fg.adj.items()] == [
        (k, dict(v)) for k, v in ng.adj.items()
    ]
    assert [dict(v) for v in fg.adj.values()] == [dict(v) for v in ng.adj.values()]
    # Mapping protocol: dict() conversion must produce a node-keyed mapping,
    # not raise ValueError or unpack neighbor tuples as (k, v) pairs.
    assert dict(fg.adj) == dict(ng.adj)


@pytest.mark.parametrize(
    "fnx_ctor",
    [fnx.Graph, fnx.DiGraph],
)
def test_adj_get_matches_upstream_defaults(fnx_ctor):
    fg = fnx_ctor()
    fg.add_edges_from([(1, 2), (2, 3)])

    assert fg.adj.get(99) is None
    assert fg.adj.get(99, "sentinel") == "sentinel"
    assert dict(fg.adj.get(1)) == {2: {}}


@pytest.mark.parametrize(
    ("fnx_ctor", "nx_ctor"),
    [
        (fnx.Graph, nx.Graph),
        (fnx.DiGraph, nx.DiGraph),
    ],
)
def test_edges_satisfies_mapping_protocol(fnx_ctor, nx_ctor):
    fg = fnx_ctor()
    fg.add_edge("a", "b", weight=3)
    fg.add_edge("b", "c", weight=5)
    ng = nx_ctor()
    ng.add_edge("a", "b", weight=3)
    ng.add_edge("b", "c", weight=5)

    for attr in ("items", "keys", "values", "get"):
        assert hasattr(fg.edges, attr), f"{fnx_ctor.__name__}.edges is missing {attr}"

    assert dict(fg.edges) == dict(ng.edges)
    assert list(fg.edges.keys()) == list(ng.edges.keys())
    assert list(fg.edges.items()) == list(ng.edges.items())
    assert list(fg.edges.values()) == list(ng.edges.values())
    assert fg.edges.get(("a", "b")) == ng.edges.get(("a", "b"))
    assert fg.edges.get(("x", "y")) is ng.edges.get(("x", "y")) is None
    assert fg.edges.get(("x", "y"), "sentinel") == ng.edges.get(
        ("x", "y"), "sentinel"
    )


@pytest.mark.parametrize(
    ("direction", "fnx_ctor", "nx_ctor"),
    [
        ("to_directed", fnx.Graph, nx.Graph),
        ("to_undirected", fnx.DiGraph, nx.DiGraph),
    ],
)
def test_conversion_live_view_adj_satisfies_mapping_protocol(direction, fnx_ctor, nx_ctor):
    from collections.abc import Mapping

    fg = fnx_ctor()
    fg.add_edges_from([(1, 2), (2, 3)])
    ng = nx_ctor()
    ng.add_edges_from([(1, 2), (2, 3)])

    fv = getattr(fg, direction)(as_view=True)
    nv = getattr(ng, direction)(as_view=True)

    # Contract: the adj view and its inner neighbor maps must be Mappings
    # (so keys/items/values/get and dict() conversion are all well-defined).
    assert isinstance(fv.adj, Mapping)
    for attr in ("items", "keys", "values", "get"):
        assert hasattr(fv.adj, attr)

    fv_deep = {k: dict(v) for k, v in fv.adj.items()}
    nv_deep = {k: dict(v) for k, v in nv.adj.items()}
    assert fv_deep == nv_deep

    # get() on a hit returns a Mapping whose content matches upstream.
    assert isinstance(fv.adj.get(1), Mapping)
    assert dict(fv.adj.get(1)) == dict(nv.adj.get(1))
    # Default on miss matches upstream.
    assert fv.adj.get(99) is nv.adj.get(99) is None
    assert fv.adj.get(99, "sentinel") == nv.adj.get(99, "sentinel")


def test_reverse_view_adj_exposes_mapping_helpers():
    fg = fnx.DiGraph()
    fg.add_edges_from([(1, 2), (2, 3), (3, 4)])
    ng = nx.DiGraph()
    ng.add_edges_from([(1, 2), (2, 3), (3, 4)])

    frv = fnx.reverse_view(fg)
    nrv = nx.reverse_view(ng)

    for attr in ("items", "keys", "values", "get"):
        assert hasattr(frv.adj, attr), f"reverse_view.adj is missing {attr}"

    assert list(frv.adj.keys()) == list(nrv.adj.keys())
    assert [(k, dict(v)) for k, v in frv.adj.items()] == [
        (k, dict(v)) for k, v in nrv.adj.items()
    ]
    assert [dict(v) for v in frv.adj.values()] == [dict(v) for v in nrv.adj.values()]
    assert frv.adj.get(99) is None
    assert frv.adj.get(99, "sentinel") == "sentinel"
