"""Parity coverage for reverse_view conversions (to_directed/to_undirected/reverse).

Bead franken_networkx-lfxu: reverse_view must expose to_directed(),
to_undirected(), and reverse(copy=...) matching upstream's surface.
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
def test_reverse_view_to_directed_matches_networkx(fnx_ctor, nx_ctor):
    fg = fnx_ctor()
    fg.add_edges_from([(1, 2), (2, 3)])
    ng = nx_ctor()
    ng.add_edges_from([(1, 2), (2, 3)])

    frv = fnx.reverse_view(fg)
    nrv = nx.reverse_view(ng)

    fd = frv.to_directed()
    nd = nrv.to_directed()
    # Materialised DiGraph / MultiDiGraph with the reversed edge set.
    assert fd.is_directed()
    assert not fd.is_multigraph() if not fg.is_multigraph() else fd.is_multigraph()
    assert sorted(fd.edges()) == sorted(nd.edges())


@pytest.mark.parametrize(
    ("fnx_ctor", "nx_ctor"),
    [
        (fnx.DiGraph, nx.DiGraph),
        (fnx.MultiDiGraph, nx.MultiDiGraph),
    ],
)
def test_reverse_view_to_undirected_matches_networkx(fnx_ctor, nx_ctor):
    fg = fnx_ctor()
    fg.add_edges_from([(1, 2), (2, 3)])
    ng = nx_ctor()
    ng.add_edges_from([(1, 2), (2, 3)])

    frv = fnx.reverse_view(fg)
    nrv = nx.reverse_view(ng)

    fu = frv.to_undirected()
    nu = nrv.to_undirected()
    assert not fu.is_directed()
    # Undirected edge set comparison (frozenset normalisation).
    assert sorted(sorted(e) for e in fu.edges()) == sorted(
        sorted(e) for e in nu.edges()
    )


@pytest.mark.parametrize(
    ("fnx_ctor", "nx_ctor"),
    [
        (fnx.DiGraph, nx.DiGraph),
        (fnx.MultiDiGraph, nx.MultiDiGraph),
    ],
)
def test_reverse_view_reverse_copy_true_returns_original_orientation(
    fnx_ctor, nx_ctor
):
    fg = fnx_ctor()
    fg.add_edges_from([(1, 2), (2, 3)])
    ng = nx_ctor()
    ng.add_edges_from([(1, 2), (2, 3)])

    frv = fnx.reverse_view(fg)
    nrv = nx.reverse_view(ng)

    fr = frv.reverse(copy=True)
    nr = nrv.reverse(copy=True)

    # Same edge set as the original graph — reverse of a reverse is a
    # copy of the original.
    assert sorted(fr.edges()) == sorted(fg.edges()) == sorted(nr.edges())
    # It's a fresh copy, not the same object.
    assert fr is not fg


@pytest.mark.parametrize(
    ("fnx_ctor", "nx_ctor"),
    [
        (fnx.DiGraph, nx.DiGraph),
        (fnx.MultiDiGraph, nx.MultiDiGraph),
    ],
)
def test_reverse_view_reverse_copy_false_returns_underlying_graph(
    fnx_ctor, nx_ctor
):
    fg = fnx_ctor()
    fg.add_edges_from([(1, 2), (2, 3)])

    frv = fnx.reverse_view(fg)
    fr = frv.reverse(copy=False)
    # reverse(copy=False) on a reverse-view returns the original
    # directed orientation as a live view — matches upstream.
    assert fr is fg


@pytest.mark.parametrize(
    ("fnx_ctor", "nx_ctor"),
    [
        (fnx.DiGraph, nx.DiGraph),
        (fnx.MultiDiGraph, nx.MultiDiGraph),
    ],
)
def test_reverse_view_adj_and_succ_are_distinct_live_wrappers(fnx_ctor, nx_ctor):
    """A reverse view has equivalent, but not aliased, adj and succ wrappers.

    The two-class parametrisation is the negative case for a naive simple-graph
    fix, while the source mutation rejects a superficially distinct snapshot.
    """
    fg, ng = fnx_ctor(), nx_ctor()
    for graph in (fg, ng):
        graph.add_edge("left", "middle")
    frv, nrv = fg.reverse(copy=False), ng.reverse(copy=False)

    assert (frv.adj is frv.succ) is (nrv.adj is nrv.succ) is False
    assert type(frv.adj).__name__ == type(nrv.adj).__name__
    assert type(frv.succ).__name__ == type(nrv.succ).__name__

    for graph in (fg, ng):
        graph.add_edge("right", "middle")
    assert list(frv.adj) == list(nrv.adj)
    assert list(frv.succ) == list(nrv.succ)


def _conversion_source(lib, graph_type, parent_kind):
    graph = getattr(lib, graph_type)()
    payload = ["original"]
    graph.graph.update(payload=payload, alias=payload)
    graph.add_nodes_from(["a", 2, ("c", 3), "isolated", "hidden"])
    graph.nodes[2].update(payload=payload, alias=payload)
    edges = [
        ("a", 2, "shared", {"weight": 2.5, "payload": payload}),
        (2, "a", "shared", {"weight": 7, "payload": payload}),
        (2, ("c", 3), "forward", {"weight": 3, "payload": payload}),
        (("c", 3), 2, "backward", {"weight": 11, "payload": payload}),
        (("c", 3), ("c", 3), "loop", {"weight": 5, "payload": payload}),
        ("hidden", "a", "hidden", {"weight": 13}),
    ]
    if graph.is_multigraph():
        graph.add_edges_from(edges)
        graph.add_edge("a", 2, key="parallel", weight=17)
    else:
        graph.add_edges_from((u, v, attrs) for u, v, _, attrs in edges)
    if parent_kind == "filtered":
        parent = graph.subgraph(["a", 2, ("c", 3), "isolated"])
    elif parent_kind == "converted":
        parent = graph.to_directed(as_view=True)
    else:
        parent = graph
    return graph, parent.reverse(copy=False)


def _conversion_state(graph):
    edges = (
        list(graph.edges(keys=True, data=True))
        if graph.is_multigraph()
        else list(graph.edges(data=True))
    )
    rows = [(node, list(graph.adj[node])) for node in graph]
    pred = [(node, list(graph.pred[node])) for node in graph] if graph.is_directed() else None
    return dict(graph.graph), list(graph.nodes(data=True)), edges, rows, pred


@pytest.mark.parametrize("graph_type", ["DiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("parent_kind", ["plain", "filtered", "converted"])
@pytest.mark.parametrize("method", ["to_directed", "to_undirected"])
def test_reverse_conversion_as_view_is_frozen_live_and_shared(graph_type, parent_kind, method):
    pairs = []
    for lib in (fnx, nx):
        source, reverse = _conversion_source(lib, graph_type, parent_kind)
        view = getattr(reverse, method)(as_view=True)
        assert lib.is_frozen(view)
        assert view._graph is reverse
        assert view.graph is source.graph
        assert view.nodes[2] is source.nodes[2]
        with pytest.raises(lib.NetworkXError):
            view.add_edge("forbidden", "mutation")
        source.graph["payload"].append("through-source")
        source.add_edge(("c", 3), "isolated", weight=19)
        if source.is_multigraph():
            source.remove_edge(2, ("c", 3), key="forward")
        else:
            source.remove_edge(2, ("c", 3))
        view.nodes[2]["through-view"] = [23]
        assert source.nodes[2]["through-view"] == [23]
        pairs.append((source, view))
    assert _conversion_state(pairs[0][1]) == _conversion_state(pairs[1][1])
    assert _conversion_state(pairs[0][0]) == _conversion_state(pairs[1][0])


@pytest.mark.parametrize("graph_type", ["DiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("parent_kind", ["plain", "filtered", "converted"])
@pytest.mark.parametrize("method", ["to_directed", "to_undirected"])
def test_reverse_conversion_copy_deepcopies_each_attribute_dictionary(graph_type, parent_kind, method):
    pairs = []
    for lib in (fnx, nx):
        source, reverse = _conversion_source(lib, graph_type, parent_kind)
        copied = getattr(reverse, method)()
        assert not lib.is_frozen(copied)
        assert copied.graph["payload"] is not source.graph["payload"]
        assert copied.graph["payload"] is copied.graph["alias"]
        assert copied.nodes[2]["payload"] is not source.nodes[2]["payload"]
        assert copied.nodes[2]["payload"] is copied.nodes[2]["alias"]
        u, v = (2, "a") if copied.is_directed() else ("a", 2)
        edge = copied[u][v]["shared"] if copied.is_multigraph() else copied[u][v]
        assert edge["payload"] is not source.graph["payload"]
        assert edge["payload"] is not copied.nodes[2]["payload"]
        assert copied.graph["payload"] is not copied.nodes[2]["payload"]
        source.graph["payload"].append("source-only")
        assert copied.nodes[2]["payload"] == ["original"]
        copied.nodes[2]["payload"].append("copy-only")
        assert source.nodes[2]["payload"] == ["original", "source-only"]
        pairs.append((source, copied))
    assert _conversion_state(pairs[0][1]) == _conversion_state(pairs[1][1])
    assert _conversion_state(pairs[0][0]) == _conversion_state(pairs[1][0])


@pytest.mark.parametrize("graph_type", ["DiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("parent_kind", ["plain", "filtered", "converted"])
@pytest.mark.parametrize("method", ["to_directed", "to_undirected"])
def test_reverse_conversion_preserves_non_string_attribute_keys(graph_type, parent_kind, method):
    results = []
    for lib in (fnx, nx):
        source, reverse = _conversion_source(lib, graph_type, parent_kind)
        edge = source["a"][2]["shared"] if source.is_multigraph() else source["a"][2]
        edge[("attribute", 1)] = [29]
        edge["key"] = [31]
        source.nodes[2][("node", 2)] = [37]
        results.append(getattr(reverse, method)())
    assert _conversion_state(results[0]) == _conversion_state(results[1])


@pytest.mark.parametrize("graph_type", ["DiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("parent_kind", ["plain", "filtered", "converted"])
@pytest.mark.parametrize("args,kwargs", [
    ((), {"reciprocal": False}),
    ((), {"reciprocal": True}),
    ((), {"reciprocal": 1}),
    ((True,), {}),
    ((True, True), {}),
    ((), {"reciprocal": True, "as_view": True}),
])
def test_reverse_undirected_reciprocal_and_positional_contract(graph_type, parent_kind, args, kwargs):
    results = []
    for lib in (fnx, nx):
        source, reverse = _conversion_source(lib, graph_type, parent_kind)
        converted = reverse.to_undirected(*args, **kwargs)
        results.append(converted)
        as_view = kwargs.get("as_view", args[1] if len(args) == 2 else False)
        assert lib.is_frozen(converted) is (as_view is True)
        source.add_edge("isolated", "a", weight=41)
    assert _conversion_state(results[0]) == _conversion_state(results[1])


@pytest.mark.parametrize("graph_type", ["DiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("method", ["to_directed", "to_undirected"])
def test_reverse_conversion_signature_matches_networkx(graph_type, method):
    import inspect

    signatures = []
    for lib in (fnx, nx):
        reverse = getattr(lib, graph_type)().reverse(copy=False)
        signatures.append(inspect.signature(getattr(reverse, method)))
    assert signatures[0] == signatures[1]


@pytest.mark.parametrize("graph_type", ["DiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("parent_kind", ["plain", "filtered", "converted"])
@pytest.mark.parametrize("kwargs", [{}, {"copy": True}])
def test_reverse_view_reverse_copy_deepcopies_payloads_and_preserves_order(graph_type, parent_kind, kwargs):
    results = []
    for lib in (fnx, nx):
        source, reverse = _conversion_source(lib, graph_type, parent_kind)
        source_edge = source["a"][2]["shared"] if source.is_multigraph() else source["a"][2]
        source_edge[("attribute", 1)] = [43]
        copied = reverse.reverse(**kwargs)
        assert not lib.is_frozen(copied)
        assert copied.graph["payload"] is not source.graph["payload"]
        assert copied.graph["payload"] is copied.graph["alias"]
        assert copied.nodes[2]["payload"] is not source.nodes[2]["payload"]
        assert copied.nodes[2]["payload"] is copied.nodes[2]["alias"]
        copied_edge = copied["a"][2]["shared"] if copied.is_multigraph() else copied["a"][2]
        assert copied_edge["payload"] is not source_edge["payload"]
        assert copied_edge["payload"] is not copied.nodes[2]["payload"]
        assert copied_edge[("attribute", 1)] is not source_edge[("attribute", 1)]
        copied.nodes[2]["payload"].append("copy-only")
        assert source.nodes[2]["payload"] == ["original"]
        source.graph["payload"].append("source-only")
        assert copied_edge["payload"] == ["original"]
        assert copied.graph["payload"] == ["original"]
        results.append((source, copied))
    assert _conversion_state(results[0][1]) == _conversion_state(results[1][1])
    assert _conversion_state(results[0][0]) == _conversion_state(results[1][0])


@pytest.mark.parametrize("graph_type", ["DiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("parent_kind", ["plain", "filtered", "converted"])
def test_reverse_view_reverse_copy_observes_node_attribute_edits_after_warm_copy(graph_type, parent_kind):
    results = []
    for lib in (fnx, nx):
        source, reverse = _conversion_source(lib, graph_type, parent_kind)
        before = reverse.reverse(copy=True)
        source.nodes[2]["new"] = [47]
        source.nodes[2]["payload"] = ["replacement"]
        source.nodes[2]["alias"] = source.nodes[2]["payload"]
        after = reverse.reverse(copy=True)
        assert "new" not in before.nodes[2]
        assert before.nodes[2]["payload"] == ["original"]
        assert after.nodes[2]["new"] == [47]
        assert after.nodes[2]["payload"] == ["replacement"]
        assert after.nodes[2]["payload"] is after.nodes[2]["alias"]
        assert after.nodes[2]["payload"] is not source.nodes[2]["payload"]
        source.nodes[2]["new"].append(53)
        assert after.nodes[2]["new"] == [47]
        results.append((before, after))
    assert _conversion_state(results[0][0]) == _conversion_state(results[1][0])
    assert _conversion_state(results[0][1]) == _conversion_state(results[1][1])
