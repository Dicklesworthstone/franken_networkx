"""Parity coverage for reverse_view adjacency mapping and item access.

Bead franken_networkx-b158: reverse_view must expose NetworkX's core
mapping interface — view.adj / view.adjacency() yield reversed-edge
adjacency with edge attributes, and view[node] returns the reversed
neighbor mapping directly.
"""

import networkx as nx
import pytest

import franken_networkx as fnx


def _deep_adjacency(view):
    return [
        (node, {nbr: dict(attrs) for nbr, attrs in inner.items()})
        for node, inner in view.adjacency()
    ]


def test_reverse_view_getitem_returns_reversed_adjacency_mapping():
    fg = fnx.DiGraph()
    fg.add_edges_from([(1, 2, {"w": 3}), (2, 3)])
    ng = nx.DiGraph()
    ng.add_edges_from([(1, 2, {"w": 3}), (2, 3)])

    frv = fnx.reverse_view(fg)
    nrv = nx.reverse_view(ng)

    # view[node] must return the reversed-neighbors mapping with edge attrs.
    assert dict(frv[2]) == dict(nrv[2])
    assert dict(frv[1]) == dict(nrv[1])
    assert dict(frv[3]) == dict(nrv[3])


def test_reverse_view_adjacency_yields_reversed_edge_attrs():
    fg = fnx.DiGraph()
    fg.add_edges_from([(1, 2, {"w": 3}), (2, 3)])
    ng = nx.DiGraph()
    ng.add_edges_from([(1, 2, {"w": 3}), (2, 3)])

    frv = fnx.reverse_view(fg)
    nrv = nx.reverse_view(ng)

    assert _deep_adjacency(frv) == _deep_adjacency(nrv)


def test_reverse_view_adj_indexing_matches_networkx():
    fg = fnx.DiGraph()
    fg.add_edges_from([(1, 2), (2, 3)])
    ng = nx.DiGraph()
    ng.add_edges_from([(1, 2), (2, 3)])

    frv = fnx.reverse_view(fg)
    nrv = nx.reverse_view(ng)

    # Going through .adj explicitly must produce the same dict.
    assert dict(frv.adj[2]) == dict(nrv.adj[2])
    assert dict(frv.adj[1]) == dict(nrv.adj[1])


def test_reverse_view_missing_node_raises():
    """view[missing_node] must raise, not return {}."""
    fg = fnx.DiGraph()
    fg.add_edges_from([(1, 2)])
    frv = fnx.reverse_view(fg)
    with pytest.raises((KeyError, fnx.NodeNotFound, nx.NodeNotFound)):
        _ = frv[99]


def test_reverse_view_exposes_nbunch_iter():
    """Bead franken_networkx-9c3f: reverse_view exposes nbunch_iter
    matching upstream for subset+unknown, None, and single-node inputs.
    """
    fg = fnx.DiGraph()
    fg.add_edges_from([(1, 2), (2, 3)])
    ng = nx.DiGraph()
    ng.add_edges_from([(1, 2), (2, 3)])
    frv = fnx.reverse_view(fg)
    nrv = nx.reverse_view(ng)

    assert hasattr(frv, "nbunch_iter")
    assert list(frv.nbunch_iter([1, 99])) == list(nrv.nbunch_iter([1, 99]))
    assert sorted(frv.nbunch_iter(None)) == sorted(nrv.nbunch_iter(None))
    assert list(frv.nbunch_iter(2)) == list(nrv.nbunch_iter(2))


_LAZY_REVERSE_KINDS = (
    "reverse",
    "filter_then_reverse",
    "reverse_then_filter",
    "key_filter_then_reverse",
    "reverse_then_key_filter",
)


def _lazy_multidigraph_reverse(lib, kind):
    graph = lib.MultiDiGraph()
    graph.add_weighted_edges_from(
        [
            ("a", "s", 5), ("t", "a", 9),
            ("s", "t", 20), ("hidden", "s", 100),
        ]
    )
    graph.add_edge("a", "s", key="parallel", weight=40)
    graph.add_edge("a", "s", key=("route", 2), weight=12)
    graph.add_edge("a", "s", key="blocked", weight=3)
    if kind == "filter_then_reverse":
        view = graph.subgraph(["s", "a", "t"]).reverse(copy=False)
    elif kind == "reverse_then_filter":
        view = graph.reverse(copy=False).subgraph(["s", "a", "t"])
    elif kind == "key_filter_then_reverse":
        view = lib.subgraph_view(
            graph, filter_node=lambda node: node != "hidden",
            filter_edge=lambda u, v, key: key != "blocked",
        ).reverse(copy=False)
    elif kind == "reverse_then_key_filter":
        view = lib.subgraph_view(
            graph.reverse(copy=False), filter_node=lambda node: node != "hidden",
            filter_edge=lambda u, v, key: key != "blocked",
        )
    else:
        view = graph.reverse(copy=False)
    return graph, view


def _reverse_pair_items(view, access):
    if access == "getitem":
        return list(view["s"]["a"].items())
    if access in ("pred", "_pred"):
        return list(getattr(view, access)["a"]["s"].items())
    if access == "adjacency":
        return list(dict(view.adjacency())["s"]["a"].items())
    if access == "edges":
        return [
            (key, attrs) for u, v, key, attrs in view.edges(keys=True, data=True)
            if (u, v) == ("s", "a")
        ]
    return list(getattr(view, access)["s"]["a"].items())


@pytest.mark.parametrize("kind", _LAZY_REVERSE_KINDS)
@pytest.mark.parametrize("access", ["getitem", "adj", "pred", "_adj", "_pred", "adjacency", "edges"])
def test_lazy_reverse_multidigraph_attributes_write_through(kind, access):
    def mutate(lib):
        graph, view = _lazy_multidigraph_reverse(lib, kind)
        # Read through the view before touching any base-graph attribute view:
        # lazy native dictionaries must be live on their very first exposure.
        items = _reverse_pair_items(view, access)
        for key, attrs in items:
            attrs["visited"] = True
            attrs["weight"] += 0.25
            assert attrs is graph.get_edge_data("a", "s", key)
        return (
            list(view),
            [key for key, _ in items],
            [(u, v, key, dict(attrs)) for u, v, key, attrs in graph.edges(keys=True, data=True)],
        )

    expected = mutate(nx)
    assert mutate(fnx) == expected


@pytest.mark.parametrize("direction", ["adj", "pred"])
@pytest.mark.parametrize("mutation", ["add", "remove", "remove_readd"])
def test_lazy_reverse_multidigraph_held_parallel_keys_remain_live(direction, mutation):
    def mutate(lib):
        graph, view = _lazy_multidigraph_reverse(lib, "reverse")
        held = view.adj["s"]["a"] if direction == "adj" else view.pred["a"]["s"]
        if mutation == "add":
            graph.add_edge("a", "s", key=("new", 3), weight=7)
        elif mutation == "remove":
            graph.remove_edge("a", "s", key="parallel")
        else:
            for key in (0, "parallel", ("route", 2), "blocked"):
                graph.remove_edge("a", "s", key=key)
            graph.add_edge("a", "s", key="replacement", weight=8)
        fresh = view.adj["s"]["a"] if direction == "adj" else view.pred["a"]["s"]
        return (
            [(key, dict(attrs)) for key, attrs in held.items()],
            [(key, dict(attrs)) for key, attrs in fresh.items()],
        )

    assert mutate(fnx) == mutate(nx)


@pytest.mark.parametrize("kind", _LAZY_REVERSE_KINDS)
def test_lazy_reverse_multidigraph_weight_callback_changes_path_lengths(kind):
    from networkx.algorithms.shortest_paths.weighted import _dijkstra_multisource

    def distances(lib):
        graph, view = _lazy_multidigraph_reverse(lib, kind)

        def weight(u, v, keyed_attrs):
            for attrs in keyed_attrs.values():
                attrs["weight"] = 1
            # A callback may read the same original edges after updating the
            # dictionaries it received. A detached snapshot returns old costs.
            key = "parallel" if "parallel" in keyed_attrs else next(iter(keyed_attrs))
            return graph.get_edge_data(v, u, key)["weight"]

        # Exercise both graph surfaces through the same reference Python
        # search so backend dispatch cannot convert away the view under test.
        return _dijkstra_multisource(view, ["s"], weight)

    expected = distances(nx)
    assert expected["a"] == 1
    assert expected["t"] == 2
    assert distances(fnx) == expected
