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


@pytest.mark.parametrize("builder_name", ["restricted_view", "subgraph_view"])
def test_filtered_graph_view_edges_data_helper_matches_upstream(builder_name):
    fg = fnx.Graph()
    fg.add_edges_from([(1, 2, {"w": 3}), (2, 3, {"w": 5}), (3, 4)])
    ng = nx.Graph()
    ng.add_edges_from([(1, 2, {"w": 3}), (2, 3, {"w": 5}), (3, 4)])
    if builder_name == "restricted_view":
        fv = fnx.restricted_view(fg, [], [])
        nv = nx.restricted_view(ng, [], [])
    else:
        fv = fnx.subgraph_view(fg)
        nv = nx.subgraph_view(ng)

    assert hasattr(fv.edges, "data")
    assert list(fv.edges.data()) == list(nv.edges.data())
    assert list(fv.edges.data("w")) == list(nv.edges.data("w"))
    assert list(fv.edges.data("missing", default=0)) == list(
        nv.edges.data("missing", default=0)
    )


@pytest.mark.parametrize("builder_name", ["restricted_view", "subgraph_view"])
def test_filtered_graph_view_adjacency_preserves_mapping_contract(builder_name):
    from collections.abc import Mapping

    fg = fnx.Graph()
    fg.add_nodes_from(["a", "b", "c"])
    fg.add_edge("a", "c")
    ng = nx.Graph()
    ng.add_nodes_from(["a", "b", "c"])
    ng.add_edge("a", "c")
    if builder_name == "restricted_view":
        fv = fnx.restricted_view(fg, [], [])
        nv = nx.restricted_view(ng, [], [])
    else:
        fv = fnx.subgraph_view(fg)
        nv = nx.subgraph_view(ng)

    fnx_adj = list(fv.adjacency())
    nx_adj = list(nv.adjacency())

    # Same node order and count.
    assert [n for n, _ in fnx_adj] == [n for n, _ in nx_adj]
    # Each neighbor bundle is a Mapping (upstream returns FilterAtlas; we return dict).
    # Both must satisfy the Mapping contract and compare equal on content.
    for (fn, fv_), (nn, nv_) in zip(fnx_adj, nx_adj):
        assert isinstance(fv_, Mapping)
        assert dict(fv_) == dict(nv_)


@pytest.mark.parametrize(
    ("fnx_ctor", "nx_ctor"),
    [
        (fnx.Graph, nx.Graph),
        (fnx.DiGraph, nx.DiGraph),
    ],
)
def test_edge_subgraph_returns_frozen_view_with_atlas_like_adj(fnx_ctor, nx_ctor):
    from collections.abc import Mapping

    fg = fnx_ctor()
    fg.add_edge("a", "b", weight=3)
    fg.add_edge("b", "c", weight=5)
    ng = nx_ctor()
    ng.add_edge("a", "b", weight=3)
    ng.add_edge("b", "c", weight=5)

    fh = fg.edge_subgraph([("a", "b")])
    nh = ng.edge_subgraph([("a", "b")])

    # Both should be frozen.
    assert fnx.is_frozen(fh) == nx.is_frozen(nh) is True

    # H['a'] and H.adj['a'] return Mapping objects (AtlasView upstream,
    # _FilteredNeighborMap here) that reject __setitem__.
    for accessor in (lambda g, n: g[n], lambda g, n: g.adj[n]):
        fnbrs = accessor(fh, "a")
        nnbrs = accessor(nh, "a")
        assert isinstance(fnbrs, Mapping)
        with pytest.raises(TypeError):
            fnbrs["x"] = {}
        with pytest.raises(TypeError):
            nnbrs["x"] = {}
        assert dict(fnbrs) == dict(nnbrs)

    # Edge set matches upstream.
    assert list(fh.edges) == list(nh.edges)


@pytest.mark.parametrize(
    ("fnx_ctor", "nx_ctor"),
    [
        (fnx.MultiGraph, nx.MultiGraph),
        (fnx.MultiDiGraph, nx.MultiDiGraph),
    ],
)
def test_multigraph_adj_mapping_helpers_preserve_adjacency_view_layers(fnx_ctor, nx_ctor):
    from collections.abc import Mapping

    fg = fnx_ctor()
    fg.add_edge("a", "b", weight=3)
    fg.add_edge("b", "c", weight=5)
    ng = nx_ctor()
    ng.add_edge("a", "b", weight=3)
    ng.add_edge("b", "c", weight=5)

    # Outer values are Mapping (AdjacencyView/MultiAdjacencyView), not raw dicts.
    for (fk, fv), (nk, nv) in zip(fg.adj.items(), ng.adj.items()):
        assert fk == nk
        assert isinstance(fv, Mapping)
        assert isinstance(nv, Mapping)
        with pytest.raises(TypeError):
            fv["x"] = {}
        with pytest.raises(TypeError):
            nv["x"] = {}
    for fv, nv in zip(fg.adj.values(), ng.adj.values()):
        assert isinstance(fv, Mapping)
        with pytest.raises(TypeError):
            fv["x"] = {}

    # Deep content matches upstream.
    fdeep = {k: {kk: dict(vv) for kk, vv in dict(v).items()} for k, v in fg.adj.items()}
    ndeep = {k: {kk: dict(vv) for kk, vv in dict(v).items()} for k, v in ng.adj.items()}
    assert fdeep == ndeep


@pytest.mark.parametrize("attr_name", ["succ", "pred"])
def test_multidigraph_succ_and_pred_preserve_adjacency_view_helpers(attr_name):
    from collections.abc import Mapping

    fg = fnx.MultiDiGraph()
    fg.add_edge(1, 2, weight=3)
    fg.add_edge(2, 3)
    ng = nx.MultiDiGraph()
    ng.add_edge(1, 2, weight=3)
    ng.add_edge(2, 3)

    fa = getattr(fg, attr_name)
    na = getattr(ng, attr_name)

    for attr in ("items", "keys", "values", "get"):
        assert hasattr(fa, attr)

    # Outer values should be AdjacencyView-style Mappings that reject mutation.
    for (fk, fv), (nk, nv) in zip(fa.items(), na.items()):
        assert fk == nk
        assert isinstance(fv, Mapping)
        with pytest.raises(TypeError):
            fv["x"] = {}
        with pytest.raises(TypeError):
            nv["x"] = {}

    # Deep content matches upstream through the full three-layer stack.
    fdeep = {k: {kk: dict(vv) for kk, vv in dict(v).items()} for k, v in fa.items()}
    ndeep = {k: {kk: dict(vv) for kk, vv in dict(v).items()} for k, v in na.items()}
    assert fdeep == ndeep


@pytest.mark.parametrize(
    ("direction", "fnx_ctor", "nx_ctor"),
    [
        ("to_directed", fnx.Graph, nx.Graph),
        ("to_undirected", fnx.DiGraph, nx.DiGraph),
    ],
)
def test_conversion_live_view_adj_mapping_helpers_deep_match(direction, fnx_ctor, nx_ctor):
    fg = fnx_ctor()
    fg.add_edges_from([(1, 2), (2, 3)])
    ng = nx_ctor()
    ng.add_edges_from([(1, 2), (2, 3)])

    fv = getattr(fg, direction)(as_view=True)
    nv = getattr(ng, direction)(as_view=True)

    fdeep_items = [(k, {kk: dict(vv) for kk, vv in dict(v).items()}) for k, v in fv.adj.items()]
    ndeep_items = [(k, {kk: dict(vv) for kk, vv in dict(v).items()}) for k, v in nv.adj.items()]
    assert fdeep_items == ndeep_items

    fdeep_values = [{kk: dict(vv) for kk, vv in dict(v).items()} for v in fv.adj.values()]
    ndeep_values = [{kk: dict(vv) for kk, vv in dict(v).items()} for v in nv.adj.values()]
    assert fdeep_values == ndeep_values


@pytest.mark.parametrize("builder_name", ["restricted_view", "subgraph_view"])
def test_filtered_graph_view_adj_mapping_helpers_deep_match(builder_name):
    fg = fnx.Graph()
    fg.add_edges_from([(1, 2), (2, 3)])
    ng = nx.Graph()
    ng.add_edges_from([(1, 2), (2, 3)])
    if builder_name == "restricted_view":
        fv = fnx.restricted_view(fg, [], [])
        nv = nx.restricted_view(ng, [], [])
    else:
        fv = fnx.subgraph_view(fg)
        nv = nx.subgraph_view(ng)

    fdeep = [(k, {kk: dict(vv) for kk, vv in dict(v).items()}) for k, v in fv.adj.items()]
    ndeep = [(k, {kk: dict(vv) for kk, vv in dict(v).items()}) for k, v in nv.adj.items()]
    assert fdeep == ndeep


@pytest.mark.parametrize("attr_name", ["succ", "pred"])
def test_digraph_succ_and_pred_expose_mapping_helpers(attr_name):
    fg = fnx.DiGraph()
    fg.add_edges_from([(1, 2), (2, 3), (3, 4)])
    ng = nx.DiGraph()
    ng.add_edges_from([(1, 2), (2, 3), (3, 4)])

    fa = getattr(fg, attr_name)
    na = getattr(ng, attr_name)

    for attr in ("items", "keys", "values", "get"):
        assert hasattr(fa, attr)

    assert list(fa.keys()) == list(na.keys())
    assert [(k, dict(v)) for k, v in fa.items()] == [(k, dict(v)) for k, v in na.items()]
    assert [dict(v) for v in fa.values()] == [dict(v) for v in na.values()]
    assert fa.get(99) is na.get(99) is None
    assert fa.get(99, "sentinel") == na.get(99, "sentinel")
    assert dict(fa.get(1)) == dict(na.get(1))
    # dict() conversion must produce a node-keyed mapping, not raise ValueError
    # or unpack neighbor tuples as (k, v) pairs.
    assert dict(fa) == dict(na)


@pytest.mark.parametrize(
    ("fnx_ctor", "nx_ctor"),
    [
        (fnx.Graph, nx.Graph),
        (fnx.DiGraph, nx.DiGraph),
    ],
)
def test_edge_subgraph_adj_exposes_mapping_helpers(fnx_ctor, nx_ctor):
    fg = fnx_ctor()
    fg.add_edges_from([(1, 2), (2, 3), (3, 4)])
    ng = nx_ctor()
    ng.add_edges_from([(1, 2), (2, 3), (3, 4)])

    fh = fg.edge_subgraph([(1, 2), (2, 3)])
    nh = ng.edge_subgraph([(1, 2), (2, 3)])

    for attr in ("items", "keys", "values", "get"):
        assert hasattr(fh.adj, attr)

    assert list(fh.adj.keys()) == list(nh.adj.keys())
    fdeep = [(k, {kk: dict(vv) for kk, vv in dict(v).items()}) for k, v in fh.adj.items()]
    ndeep = [(k, {kk: dict(vv) for kk, vv in dict(v).items()}) for k, v in nh.adj.items()]
    assert fdeep == ndeep
    assert fh.adj.get(99) is nh.adj.get(99) is None
    assert dict(fh.adj.get(1)) == dict(nh.adj.get(1))


@pytest.mark.parametrize(
    ("fnx_ctor", "nx_ctor"),
    [
        (fnx.MultiGraph, nx.MultiGraph),
        (fnx.MultiDiGraph, nx.MultiDiGraph),
    ],
)
def test_multigraph_edges_satisfies_keyed_mapping_protocol(fnx_ctor, nx_ctor):
    fg = fnx_ctor()
    fg.add_edge("a", "b", key="k1", weight=3)
    fg.add_edge("b", "c", key="k2", weight=5)
    ng = nx_ctor()
    ng.add_edge("a", "b", key="k1", weight=3)
    ng.add_edge("b", "c", key="k2", weight=5)

    for attr in ("items", "keys", "values", "get"):
        assert hasattr(fg.edges, attr)

    # dict() must produce {(u, v, k): attrs}, not {u: v}.
    assert dict(fg.edges) == dict(ng.edges)
    assert list(fg.edges.keys()) == list(ng.edges.keys())
    assert list(fg.edges.items()) == list(ng.edges.items())
    assert list(fg.edges.values()) == list(ng.edges.values())

    # __getitem__ with keyed 3-tuple returns edge attrs.
    assert fg.edges[("a", "b", "k1")] == ng.edges[("a", "b", "k1")]
    # get() matches upstream on hit / miss / sentinel.
    assert fg.edges.get(("a", "b", "k1")) == ng.edges.get(("a", "b", "k1"))
    assert fg.edges.get(("x", "y", "z")) is ng.edges.get(("x", "y", "z")) is None
    assert fg.edges.get(("x", "y", "z"), "sentinel") == ng.edges.get(
        ("x", "y", "z"), "sentinel"
    )


@pytest.mark.parametrize(
    ("fnx_ctor", "nx_ctor"),
    [
        (fnx.MultiGraph, nx.MultiGraph),
        (fnx.MultiDiGraph, nx.MultiDiGraph),
    ],
)
def test_multigraph_adj_satisfies_mapping_protocol(fnx_ctor, nx_ctor):
    from collections.abc import Mapping

    fg = fnx_ctor()
    fg.add_edge("a", "b", weight=3)
    fg.add_edge("b", "c")
    ng = nx_ctor()
    ng.add_edge("a", "b", weight=3)
    ng.add_edge("b", "c")

    for attr in ("items", "keys", "values", "get"):
        assert hasattr(fg.adj, attr)

    # dict() must produce {node: adjacency-view-like}, not unpack 2-tuples.
    fdeep = {k: {kk: dict(vv) for kk, vv in dict(v).items()} for k, v in fg.adj.items()}
    ndeep = {k: {kk: dict(vv) for kk, vv in dict(v).items()} for k, v in ng.adj.items()}
    assert fdeep == ndeep

    # get() returns Mapping on hit, None on miss.
    fv = fg.adj.get("a")
    nv = ng.adj.get("a")
    assert isinstance(fv, Mapping)
    assert {k: dict(v) for k, v in dict(fv).items()} == {
        k: dict(v) for k, v in dict(nv).items()
    }
    assert fg.adj.get("missing") is ng.adj.get("missing") is None


@pytest.mark.parametrize(
    ("fnx_ctor", "nx_ctor"),
    [
        (fnx.MultiGraph, nx.MultiGraph),
        (fnx.MultiDiGraph, nx.MultiDiGraph),
    ],
)
def test_multigraph_nodes_satisfies_mapping_protocol(fnx_ctor, nx_ctor):
    fg = fnx_ctor()
    fg.add_node("a", color="red")
    fg.add_node("b")
    ng = nx_ctor()
    ng.add_node("a", color="red")
    ng.add_node("b")

    for attr in ("items", "keys", "values", "get"):
        assert hasattr(fg.nodes, attr)

    # dict() must produce {node: attrs}, not raise ValueError.
    assert dict(fg.nodes) == dict(ng.nodes)
    assert list(fg.nodes.keys()) == list(ng.nodes.keys())
    assert list(fg.nodes.items()) == list(ng.nodes.items())
    assert list(fg.nodes.values()) == list(ng.nodes.values())
    assert fg.nodes.get("a") == ng.nodes.get("a")
    assert fg.nodes.get("missing") is ng.nodes.get("missing") is None


def test_digraph_edge_subgraph_preserves_node_iteration_order():
    fg = fnx.DiGraph()
    fg.add_edge("a", "b")
    fg.add_edge("b", "c")
    ng = nx.DiGraph()
    ng.add_edge("a", "b")
    ng.add_edge("b", "c")

    # Each selected edge produces the same node ordering as upstream.
    assert list(fg.edge_subgraph([("a", "b")])) == list(ng.edge_subgraph([("a", "b")]))
    assert list(fg.edge_subgraph([("b", "c")])) == list(ng.edge_subgraph([("b", "c")]))
    assert list(fg.edge_subgraph([("a", "b"), ("b", "c")])) == list(
        ng.edge_subgraph([("a", "b"), ("b", "c")])
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
