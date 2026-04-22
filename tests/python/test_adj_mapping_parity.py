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


@pytest.mark.parametrize(
    ("direction", "fnx_ctor", "nx_ctor"),
    [
        ("to_directed", fnx.Graph, nx.Graph),
        ("to_undirected", fnx.DiGraph, nx.DiGraph),
    ],
)
def test_conversion_live_view_edges_satisfies_mapping_protocol(
    direction, fnx_ctor, nx_ctor
):
    fg = fnx_ctor()
    fg.add_edge("a", "b", weight=3)
    fg.add_edge("b", "c", weight=5)
    ng = nx_ctor()
    ng.add_edge("a", "b", weight=3)
    ng.add_edge("b", "c", weight=5)

    fv = getattr(fg, direction)(as_view=True)
    nv = getattr(ng, direction)(as_view=True)

    for attr in ("items", "keys", "values", "get"):
        assert hasattr(fv.edges, attr)

    # dict() conversion must produce {(u, v): attrs}, not {u: v}.
    assert dict(fv.edges) == dict(nv.edges)
    assert list(fv.edges.keys()) == list(nv.edges.keys())
    assert list(fv.edges.items()) == list(nv.edges.items())
    assert list(fv.edges.values()) == list(nv.edges.values())

    # get() tuple-key lookup matches upstream on hit and miss.
    assert fv.edges.get(("a", "b")) == nv.edges.get(("a", "b"))
    assert fv.edges.get(("b", "a")) == nv.edges.get(("b", "a"))
    assert fv.edges.get(("x", "y")) is nv.edges.get(("x", "y")) is None
    assert fv.edges.get(("x", "y"), "sentinel") == nv.edges.get(
        ("x", "y"), "sentinel"
    )

    # __contains__ matches upstream.
    assert (("a", "b") in fv.edges) is (("a", "b") in nv.edges)
    assert (("b", "a") in fv.edges) is (("b", "a") in nv.edges)
    assert (("x", "y") in fv.edges) is (("x", "y") in nv.edges)


@pytest.mark.parametrize(
    ("direction", "fnx_ctor", "nx_ctor"),
    [
        ("to_directed", fnx.Graph, nx.Graph),
        ("to_undirected", fnx.DiGraph, nx.DiGraph),
    ],
)
def test_conversion_live_view_edges_data_helper_matches_upstream(
    direction, fnx_ctor, nx_ctor
):
    fg = fnx_ctor()
    fg.add_edge("a", "b", weight=3)
    fg.add_edge("b", "c", weight=5)
    ng = nx_ctor()
    ng.add_edge("a", "b", weight=3)
    ng.add_edge("b", "c", weight=5)

    fv = getattr(fg, direction)(as_view=True)
    nv = getattr(ng, direction)(as_view=True)

    assert hasattr(fv.edges, "data")
    # Default: 3-tuples (u, v, attrs)
    assert list(fv.edges.data()) == list(nv.edges.data())
    # Named attribute projection
    assert list(fv.edges.data("weight")) == list(nv.edges.data("weight"))
    # Named attribute with default for missing
    assert list(fv.edges.data("missing", default="NA")) == list(
        nv.edges.data("missing", default="NA")
    )


def test_reverse_view_edges_exposes_edge_view_object():
    fg = fnx.DiGraph()
    fg.add_edges_from([(1, 2, {"w": 3}), (2, 3, {"w": 5})])
    ng = nx.DiGraph()
    ng.add_edges_from([(1, 2, {"w": 3}), (2, 3, {"w": 5})])

    frv = fnx.reverse_view(fg)
    nrv = nx.reverse_view(ng)

    # Must be an object, not a bound method.
    assert type(frv.edges).__name__ != "method"
    # Callable like upstream's OutEdgeView.
    assert callable(frv.edges)
    # Full mapping / edge-view surface.
    for attr in ("data", "items", "keys", "values", "get"):
        assert hasattr(frv.edges, attr)

    # Parity against networkx.
    assert list(frv.edges) == list(nrv.edges)
    assert list(frv.edges.data()) == list(nrv.edges.data())
    assert list(frv.edges.data("w")) == list(nrv.edges.data("w"))
    assert list(frv.edges.data("missing", default=0)) == list(
        nrv.edges.data("missing", default=0)
    )
    assert list(frv.edges(data=True)) == list(nrv.edges(data=True))
    assert dict(frv.edges) == dict(nrv.edges)
    assert len(frv.edges) == len(nrv.edges)

    # Mapping protocol.
    assert frv.edges.get((2, 1)) == nrv.edges.get((2, 1))
    assert frv.edges.get((99, 99)) is nrv.edges.get((99, 99)) is None
    assert (((2, 1) in frv.edges) is ((2, 1) in nrv.edges))
    assert (((1, 2) in frv.edges) is ((1, 2) in nrv.edges))
    assert (((99, 99) in frv.edges) is ((99, 99) in nrv.edges))


@pytest.mark.parametrize(
    "builder",
    [
        lambda fg: fnx.restricted_view(fg, [], []),
        lambda fg: fnx.subgraph_view(fg),
    ],
    ids=["restricted_view", "subgraph_view"],
)
def test_filtered_graph_view_edges_expose_edge_view_object(builder):
    fg = fnx.Graph()
    fg.add_edges_from([(1, 2, {"w": 3}), (2, 3, {"w": 5}), (3, 4)])
    ng = nx.Graph()
    ng.add_edges_from([(1, 2, {"w": 3}), (2, 3, {"w": 5}), (3, 4)])
    # Matching upstream builders.
    upstream = {
        "restricted_view": lambda g: nx.restricted_view(g, [], []),
        "subgraph_view": lambda g: nx.subgraph_view(g),
    }
    # Pick the upstream builder using the fnx builder's identity.
    # The parametrize ids carry this through.
    fv = builder(fg)
    # Hack: read the test id from the caller's frame to pick the matching nx builder.
    # Simpler: always use restricted_view([], []) for both since they're behaviourally
    # identical on this graph when no filters are applied.
    nv = nx.restricted_view(ng, [], [])

    # Must be an object, not a bound method.
    assert type(fv.edges).__name__ != "method"
    assert callable(fv.edges)
    for attr in ("data", "items", "keys", "values", "get"):
        assert hasattr(fv.edges, attr)

    assert list(fv.edges) == list(nv.edges)
    assert list(fv.edges.data()) == list(nv.edges.data())
    assert list(fv.edges.data("w")) == list(nv.edges.data("w"))
    assert dict(fv.edges) == dict(nv.edges)
    assert len(fv.edges) == len(nv.edges)
    assert ((1, 2) in fv.edges) is ((1, 2) in nv.edges)
    assert ((9, 9) in fv.edges) is ((9, 9) in nv.edges)


@pytest.mark.parametrize(
    "builder_name",
    ["restricted_view", "subgraph_view"],
)
def test_filtered_graph_view_nodes_expose_data_helper(builder_name):
    fg = fnx.Graph()
    fg.add_node("a", color="red")
    fg.add_node("b", color="blue")
    fg.add_edge("a", "c")
    ng = nx.Graph()
    ng.add_node("a", color="red")
    ng.add_node("b", color="blue")
    ng.add_edge("a", "c")
    if builder_name == "restricted_view":
        fv = fnx.restricted_view(fg, [], [])
        nv = nx.restricted_view(ng, [], [])
    else:
        fv = fnx.subgraph_view(fg)
        nv = nx.subgraph_view(ng)

    assert hasattr(fv.nodes, "data")
    assert list(fv.nodes.data()) == list(nv.nodes.data())
    assert list(fv.nodes.data("color")) == list(nv.nodes.data("color"))
    assert list(fv.nodes.data("missing", default="X")) == list(
        nv.nodes.data("missing", default="X")
    )


def test_restricted_view_with_filter_preserves_edge_view_parity():
    fg = fnx.Graph()
    fg.add_edges_from([(1, 2), (2, 3), (3, 4)])
    ng = nx.Graph()
    ng.add_edges_from([(1, 2), (2, 3), (3, 4)])

    fv = fnx.restricted_view(fg, [3], [])
    nv = nx.restricted_view(ng, [3], [])

    assert list(fv.edges) == list(nv.edges)
    assert list(fv.edges.data()) == list(nv.edges.data())


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
