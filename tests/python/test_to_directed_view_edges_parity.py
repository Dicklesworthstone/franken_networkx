"""Parity coverage for live directed/undirected conversion edge views.

Bead franken_networkx-qoz2: to_directed live views must expose
in_edges() and out_edges() matching networkx on both Graph and
MultiGraph inputs, including data= kwarg.
"""

import networkx as nx
import pytest

import franken_networkx as fnx


@pytest.mark.parametrize(
    ("fnx_ctor", "nx_ctor"),
    [
        (fnx.Graph, nx.Graph),
        (fnx.MultiGraph, nx.MultiGraph),
    ],
)
def test_to_directed_view_has_in_and_out_edges(fnx_ctor, nx_ctor):
    fg = fnx_ctor()
    fg.add_edges_from([(0, 1), (1, 2)])
    ng = nx_ctor()
    ng.add_edges_from([(0, 1), (1, 2)])

    fv = fg.to_directed(as_view=True)
    nv = ng.to_directed(as_view=True)

    assert hasattr(fv, "in_edges")
    assert hasattr(fv, "out_edges")

    # Same edge set (ordering may differ on either side, so compare sorted).
    assert sorted(fv.in_edges()) == sorted(nv.in_edges())
    assert sorted(fv.out_edges()) == sorted(nv.out_edges())


@pytest.mark.parametrize(
    ("fnx_ctor", "nx_ctor"),
    [
        (fnx.Graph, nx.Graph),
        (fnx.MultiGraph, nx.MultiGraph),
    ],
)
def test_to_directed_view_in_edges_with_data_kwarg(fnx_ctor, nx_ctor):
    fg = fnx_ctor()
    fg.add_edge(0, 1, weight=3)
    ng = nx_ctor()
    ng.add_edge(0, 1, weight=3)

    fv = fg.to_directed(as_view=True)
    nv = ng.to_directed(as_view=True)

    f_rows = sorted(fv.in_edges(data=True), key=lambda r: (r[0], r[1]))
    n_rows = sorted(nv.in_edges(data=True), key=lambda r: (r[0], r[1]))
    assert f_rows == n_rows


@pytest.mark.parametrize(
    ("fnx_ctor", "nx_ctor"),
    [
        (fnx.Graph, nx.Graph),
        (fnx.MultiGraph, nx.MultiGraph),
    ],
)
def test_to_directed_view_nbunch_argument(fnx_ctor, nx_ctor):
    """in_edges / out_edges accept an nbunch filter."""
    fg = fnx_ctor()
    fg.add_edges_from([(0, 1), (1, 2), (2, 3)])
    ng = nx_ctor()
    ng.add_edges_from([(0, 1), (1, 2), (2, 3)])

    fv = fg.to_directed(as_view=True)
    nv = ng.to_directed(as_view=True)

    assert sorted(fv.in_edges([2])) == sorted(nv.in_edges([2]))
    assert sorted(fv.out_edges([2])) == sorted(nv.out_edges([2]))


def _conversion_edge_fixture(lib, graph_class, conversion, filtered=False):
    graph = getattr(lib, graph_class)()
    options = {"key": "primary"} if graph.is_multigraph() else {}
    graph.add_edge("a", "b", weight=2, **options)
    graph.add_edge("b", "c", weight=3, **options)
    graph.add_edge("a", "a", weight=5, **options)
    graph.add_edge("hidden", "a", weight=19, **options)
    if graph.is_multigraph():
        graph.add_edge("a", "b", key=("lane", 2), weight=7)
        graph.add_edge("a", "b", key="blocked", weight=23)
    if graph.is_directed():
        graph.add_edge("b", "a", weight=11, **options)
    parent = graph
    if filtered:
        parent = lib.subgraph_view(
            graph,
            filter_node=lambda node: node != "hidden",
            filter_edge=(
                (lambda u, v, key: key != "blocked") if graph.is_multigraph()
                else (lambda u, v: True)
            ),
        )
    return graph, getattr(parent, conversion)(as_view=True)


@pytest.mark.parametrize("graph_class", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("conversion", ["to_directed", "to_undirected"])
@pytest.mark.parametrize("filtered", [False, True])
def test_conversion_edge_mappings_write_through_and_remain_live(graph_class, conversion, filtered):
    def exercise(lib):
        graph, view = _conversion_edge_fixture(lib, graph_class, conversion, filtered)
        multi = graph.is_multigraph()
        accesses = ("edges", "out_edges", "in_edges") if view.is_directed() else ("edges",)
        held = {}
        for access in accesses:
            edges = getattr(view, access)
            for edge in edges:
                u, v = edge[:2]
                key = edge[2] if multi else None
                exists = graph.has_edge(u, v, key) if multi else graph.has_edge(u, v)
                if exists:
                    original = graph.get_edge_data(u, v, key) if multi else graph.get_edge_data(u, v)
                else:
                    original = graph.get_edge_data(v, u, key) if multi else graph.get_edge_data(v, u)
                attrs = edges[edge]
                assert attrs is original
                attrs["visited"] = True
                assert original["visited"] is True
            held[access] = edges.keys(), edges.items(), edges.values()
        snapshots = []

        def snapshot():
            snapshots.append({
                access: (
                    set(keys),
                    {edge: dict(attrs) for edge, attrs in items},
                    sorted((attrs["weight"], attrs.get("visited", False)) for attrs in values),
                )
                for access, (keys, items, values) in held.items()
            })

        snapshot()
        options = {"key": "primary"} if multi else {}
        graph.add_edge("c", "d", weight=13, **options)
        snapshot()
        if multi:
            graph.add_edge("a", "b", key="later", weight=17)
            snapshot()
            graph.remove_edge("a", "b", "primary")
        else:
            graph.remove_edge("a", "b")
        snapshot()
        marker = object()
        missing = ("missing", "b", "primary") if multi else ("missing", "b")
        for access in accesses:
            assert getattr(view, access).get(missing, marker) is marker
        return snapshots

    expected = exercise(nx)
    assert exercise(fnx) == expected


@pytest.mark.parametrize("graph_class", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("conversion", ["to_directed", "to_undirected"])
def test_conversion_edge_lookup_errors_match_networkx(graph_class, conversion):
    def outcomes(lib):
        graph, view = _conversion_edge_fixture(lib, graph_class, conversion)
        if graph.is_multigraph():
            probes = [
                ("a", "b", "primary"), ("missing", "b", "primary"),
                ("a", "missing", "primary"), ("a", "b", "missing"),
                ("a", "b"), ("a", "b", "primary", "extra"),
            ]
        else:
            probes = [
                ("a", "b"), ("missing", "b"), ("a", "missing"),
                ("a",), ("a", "b", "extra"),
            ]
        probes.extend((slice(None, 2), 42))
        result = []
        for probe in probes:
            try:
                result.append(("value", dict(view.edges[probe])))
            except Exception as exc:
                result.append((type(exc).__name__, exc.args))
        return result

    assert outcomes(fnx) == outcomes(nx)


def test_undirected_multidigraph_edge_lookup_preserves_directional_precedence():
    def exercise(lib):
        graph = lib.MultiDiGraph()
        graph.add_edge("a", "b", key="shared", weight=2)
        graph.add_edge("b", "a", key="shared", weight=11)
        graph.add_edge("b", "a", key=("reverse", 1), weight=13)
        view = graph.to_undirected(as_view=True)
        forward = view.edges["a", "b", "shared"]
        backward = view.edges["b", "a", "shared"]
        reverse_only = view.edges["a", "b", ("reverse", 1)]
        assert forward is graph.get_edge_data("a", "b", "shared")
        assert backward is graph.get_edge_data("b", "a", "shared")
        assert reverse_only is graph.get_edge_data("b", "a", ("reverse", 1))
        forward["weight"], backward["weight"], reverse_only["weight"] = 3, 17, 19
        graph.remove_edge("a", "b", "shared")
        assert view.edges["a", "b", "shared"] is backward
        return {
            (u, v, key): dict(attrs)
            for u, v, key, attrs in graph.edges(keys=True, data=True)
        }

    assert exercise(fnx) == exercise(nx)


@pytest.mark.parametrize("kind", ["filtered", "filter_then_reverse", "reverse_then_filter"])
def test_undirected_conversion_edge_counts_follow_logical_topology(kind, monkeypatch):
    def exercise(lib):
        graph = lib.DiGraph()
        graph.add_nodes_from(range(4))
        graph.add_edges_from([(0, 0), (0, 1), (1, 0), (1, 2), (9, 0)])
        if kind == "reverse_then_filter":
            parent = graph.reverse(copy=False).subgraph(range(4))
        else:
            parent = graph.subgraph(range(4))
            if kind == "filter_then_reverse":
                parent = parent.reverse(copy=False)
        view = parent.to_undirected(as_view=True)
        snapshots = []

        def snapshot():
            # list/sorted request the edge view's length hint as well as its
            # iterator. Both must read the same live filtered topology.
            snapshots.append((
                view.number_of_edges(), len(view.edges), view.size(),
                sorted(view.edges), list(view.degree),
            ))

        snapshot()
        graph.add_edge(3, 2)
        graph.add_edge(2, 2)
        snapshot()
        graph.remove_edge(0, 1)
        snapshot()
        graph.remove_edge(1, 0)
        snapshot()
        if kind == "filtered":
            # Snapshot-style private rows also belong to a concrete DiGraph,
            # whose unrelated native topology must not determine its count.
            edge, loop = {}, {}
            graph._node = {0: {}, 1: {}}
            graph._succ = {0: {0: loop, 1: edge}, 1: {}}
            graph._pred = {0: {0: loop}, 1: {0: edge}}
            view = graph.to_undirected(as_view=True)
            snapshot()
        return snapshots

    expected = exercise(nx)

    def no_materialization(*args, **kwargs):
        raise AssertionError("counting a logical conversion view must not copy its graph")

    monkeypatch.setattr(fnx, "_materialize_view", no_materialization)
    assert exercise(fnx) == expected


def test_nested_directed_reverse_edge_counts_do_not_copy_parent(monkeypatch):
    def exercise(lib):
        graph = lib.Graph()
        graph.add_nodes_from(range(4))
        graph.add_edges_from([(0, 0), (0, 1), (1, 2), (2, 2), (2, 9)])
        view = graph.subgraph(range(4)).to_directed(as_view=True).reverse(copy=False)
        snapshots = []

        def snapshot():
            snapshots.append((view.number_of_edges(), len(view.edges), sorted(view.edges)))

        snapshot()
        graph.add_edge(3, 1)
        snapshot()
        graph.remove_edge(0, 0)
        snapshot()
        graph.remove_edge(1, 2)
        snapshot()
        return snapshots

    expected = exercise(nx)

    def no_materialization(*args, **kwargs):
        raise AssertionError("nested conversion/reverse counts must not copy their graph")

    monkeypatch.setattr(fnx, "_materialize_view", no_materialization)
    assert exercise(fnx) == expected
