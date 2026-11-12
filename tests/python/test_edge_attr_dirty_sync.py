import pytest

import franken_networkx as fnx


GRAPH_CASES = (
    (fnx.Graph, False),
    (fnx.DiGraph, False),
    (fnx.MultiGraph, True),
    (fnx.MultiDiGraph, True),
)


def _weighted_graph(graph_cls, is_multi):
    graph = graph_cls()
    if is_multi:
        graph.add_edge("a", "b", key=0, weight=10)
        graph.add_edge("b", "c", key=0, weight=10)
        graph.add_edge("a", "c", key=0, weight=5)
    else:
        graph.add_edge("a", "b", weight=10)
        graph.add_edge("b", "c", weight=10)
        graph.add_edge("a", "c", weight=5)
    return graph


def _set_ab_bc_to_short_path(graph, is_multi, edge_attrs):
    if is_multi:
        edge_attrs("a", "b", 0)["weight"] = 1
        edge_attrs("b", "c", 0)["weight"] = 1
    else:
        edge_attrs("a", "b")["weight"] = 1
        edge_attrs("b", "c")["weight"] = 1


def _assert_weighted_kernel_sees_mutation(graph):
    assert fnx.shortest_path(graph, "a", "c", weight="weight") == ["a", "b", "c"]
    assert fnx.bidirectional_dijkstra(graph, "a", "c", weight="weight") == (
        2,
        ["a", "b", "c"],
    )
    assert fnx.shortest_path_length(graph, "a", "c", weight="weight") == 2
    assert fnx.dijkstra_path_length(graph, "a", "c", weight="weight") == 2


@pytest.mark.parametrize(("graph_cls", "is_multi"), GRAPH_CASES)
def test_weight_mutation_via_getitem_syncs_to_weighted_kernel(graph_cls, is_multi):
    graph = _weighted_graph(graph_cls, is_multi)
    _set_ab_bc_to_short_path(graph, is_multi, lambda u, v, key=None: graph[u][v][key] if is_multi else graph[u][v])

    _assert_weighted_kernel_sees_mutation(graph)


@pytest.mark.parametrize(("graph_cls", "is_multi"), GRAPH_CASES)
def test_weight_mutation_via_edges_data_syncs_to_weighted_kernel(graph_cls, is_multi):
    graph = _weighted_graph(graph_cls, is_multi)
    if is_multi:
        for u, v, key, attrs in graph.edges(keys=True, data=True):
            if (u, v, key) in {("a", "b", 0), ("b", "c", 0)}:
                attrs["weight"] = 1
    else:
        for u, v, attrs in graph.edges(data=True):
            if (u, v) in {("a", "b"), ("b", "c")}:
                attrs["weight"] = 1

    _assert_weighted_kernel_sees_mutation(graph)


@pytest.mark.parametrize(("graph_cls", "is_multi"), GRAPH_CASES)
def test_weight_mutation_via_adjacency_syncs_to_weighted_kernel(graph_cls, is_multi):
    graph = _weighted_graph(graph_cls, is_multi)
    _set_ab_bc_to_short_path(graph, is_multi, lambda u, v, key=None: graph.adj[u][v][key] if is_multi else graph.adj[u][v])

    _assert_weighted_kernel_sees_mutation(graph)


@pytest.mark.parametrize(("graph_cls", "is_multi"), GRAPH_CASES)
def test_weight_mutation_via_get_edge_data_syncs_to_weighted_kernel(graph_cls, is_multi):
    graph = _weighted_graph(graph_cls, is_multi)
    _set_ab_bc_to_short_path(
        graph,
        is_multi,
        lambda u, v, key=None: graph.get_edge_data(u, v, key=key) if is_multi else graph.get_edge_data(u, v),
    )

    _assert_weighted_kernel_sees_mutation(graph)


@pytest.mark.parametrize(("graph_cls", "is_multi"), ((fnx.DiGraph, False), (fnx.MultiDiGraph, True)))
def test_weight_mutation_via_predecessor_adjacency_syncs_to_weighted_kernel(graph_cls, is_multi):
    graph = _weighted_graph(graph_cls, is_multi)
    _set_ab_bc_to_short_path(graph, is_multi, lambda u, v, key=None: graph.pred[v][u][key] if is_multi else graph.pred[v][u])

    _assert_weighted_kernel_sees_mutation(graph)


@pytest.mark.parametrize(("graph_cls", "is_multi"), GRAPH_CASES)
def test_weight_mutation_via_edgeview_subscript_syncs_to_weighted_kernel(graph_cls, is_multi):
    # ``G.edges[u, v]`` (EdgeView subscript) is a distinct mutable-attr
    # handout path from ``G[u][v]`` and ``G.adj[u][v]`` — the dirty marker
    # must fire here too or the skip drops the mutation.
    graph = _weighted_graph(graph_cls, is_multi)
    _set_ab_bc_to_short_path(
        graph,
        is_multi,
        lambda u, v, key=None: graph.edges[u, v, key] if is_multi else graph.edges[u, v],
    )

    _assert_weighted_kernel_sees_mutation(graph)


@pytest.mark.parametrize(("graph_cls", "is_multi"), GRAPH_CASES)
def test_set_edge_attributes_syncs_to_weighted_kernel(graph_cls, is_multi):
    # The ``set_edge_attributes`` module function mutates edge dicts in bulk;
    # it must route through a dirtying handout path.
    graph = _weighted_graph(graph_cls, is_multi)
    if is_multi:
        fnx.set_edge_attributes(graph, {("a", "b", 0): 1, ("b", "c", 0): 1}, "weight")
    else:
        fnx.set_edge_attributes(graph, {("a", "b"): 1, ("b", "c"): 1}, "weight")

    _assert_weighted_kernel_sees_mutation(graph)


@pytest.mark.parametrize(("graph_cls", "is_multi"), GRAPH_CASES)
def test_remutation_after_kernel_resyncs(graph_cls, is_multi):
    # Regression guard for the historical failure mode (g5ifq / first
    # dirty-skip): the dirty marker must remain correct *across* a weighted
    # kernel dispatch. Run a kernel first (which may clear the marker), then
    # mutate again and run another kernel — the second mutation must be seen.
    graph = _weighted_graph(graph_cls, is_multi)
    # First kernel run: shortest a->c is the direct edge (weight 5).
    assert fnx.shortest_path_length(graph, "a", "c", weight="weight") == 5
    # Second mutation, after the marker may have been reset by the first run.
    _set_ab_bc_to_short_path(graph, is_multi, lambda u, v, key=None: graph[u][v][key] if is_multi else graph[u][v])
    _assert_weighted_kernel_sees_mutation(graph)


def test_multidigraph_indexed_dirty_mark_broadens_after_node_renumbering():
    """A stale endpoint position must not mark a different edge at sync time.

    Warm the held keydict so its second subscript takes the indexed path, then
    remove two earlier isolated nodes. The old `(source, target)` positions now
    name the decoy edge. A naive deferred conversion would sync that decoy and
    silently lose the live mutation on ``u -> v``; a sequence-stamped queue
    must broaden to the existing all-mirrors fallback instead.
    """
    graph = fnx.MultiDiGraph()
    drop_a, drop_b, u, v, decoy_u, decoy_v = "drop-a", "drop-b", "u", "v", "x", "y"
    graph.add_nodes_from((drop_a, drop_b, u, v, decoy_u, decoy_v))
    graph.add_edge(u, v, key=0, weight=10)
    graph.add_edge(decoy_u, decoy_v, key=0, weight=100)

    cell = graph.adj[u][v]
    cell[0]  # fill the keyed lookaside through the string path
    assert fnx.shortest_path_length(graph, u, v, weight="weight") == 10  # reset dirty state

    cell[0]["weight"] = 1  # queued indexed dirty mark at the old positions
    graph.remove_node(drop_a)
    graph.remove_node(drop_b)

    assert fnx.shortest_path_length(graph, u, v, weight="weight") == 1


# br-r37-c1-urjxk: a dict HELD across a native call. The native call syncs the
# escaped dicts into the store and used to lift the dirty bit; a later write
# through the held reference runs no exposure site, so every following native
# read used the first call's weights. networkx is live, so each row compares
# against it: the value before the write, after it, and after the references
# are DROPPED (a fix that trusts the store once nobody holds a dict would
# lose a write made while one was held).

import networkx as nx  # noqa: E402

_HOLD_ROUTES = {
    "getitem": lambda g, u, v, multi: g[u][v][0] if multi else g[u][v],
    "edges-subscript": lambda g, u, v, multi: g.edges[u, v, 0] if multi else g.edges[u, v],
    "adj": lambda g, u, v, multi: g.adj[u][v][0] if multi else g.adj[u][v],
    "get_edge_data": lambda g, u, v, multi: g.get_edge_data(u, v, key=0) if multi else g.get_edge_data(u, v),
    "edges-data": lambda g, u, v, multi: next(
        e[-1]
        for e in (g.edges(keys=True, data=True) if multi else g.edges(data=True))
        if (e[0], e[1]) in {(u, v), (v, u)} and (not multi or e[2] == 0)
    ),
}

_WRITES = {
    "assign": lambda d: d.__setitem__("weight", 1),
    "update": lambda d: d.update(weight=1),
    "delete": lambda d: d.pop("weight"),  # networkx's default weight is 1
    "clear": lambda d: d.clear(),
}


def _weighted_twin(lib, cls_name, is_multi):
    graph = getattr(lib, cls_name)()
    for u, v, w in (("a", "b", 10), ("b", "c", 10), ("a", "c", 5)):
        if is_multi:
            graph.add_edge(u, v, key=0, weight=w)
        else:
            graph.add_edge(u, v, weight=w)
    return graph


def _weighted_reads(lib, graph):
    return (
        lib.shortest_path_length(graph, "a", "c", weight="weight"),
        lib.dijkstra_path_length(graph, "a", "c"),
        graph.size(weight="weight"),
        sorted(graph.degree(weight="weight")),
        lib.to_numpy_array(graph, nodelist=["a", "b", "c"], dtype=float).tolist(),
    )


@pytest.mark.parametrize("write", sorted(_WRITES))
@pytest.mark.parametrize("route", sorted(_HOLD_ROUTES))
@pytest.mark.parametrize(
    ("cls_name", "is_multi"),
    (("Graph", False), ("DiGraph", False), ("MultiGraph", True), ("MultiDiGraph", True)),
)
def test_a_write_through_a_dict_held_across_a_native_call_is_seen(cls_name, is_multi, route, write):
    outcomes = []
    for lib in (fnx, nx):
        graph = _weighted_twin(lib, cls_name, is_multi)
        held = [_HOLD_ROUTES[route](graph, u, v, is_multi) for u, v in (("a", "b"), ("b", "c"))]
        before = _weighted_reads(lib, graph)
        for attrs in held:
            _WRITES[write](attrs)
        after = _weighted_reads(lib, graph)
        del held, attrs
        dropped = _weighted_reads(lib, graph)
        outcomes.append((before, after, dropped))
    assert outcomes[0] == outcomes[1]


@pytest.mark.parametrize(
    ("cls_name", "is_multi"),
    (("Graph", False), ("DiGraph", False), ("MultiGraph", True), ("MultiDiGraph", True)),
)
def test_writes_between_repeated_native_calls_are_each_seen(cls_name, is_multi):
    outcomes = []
    for lib in (fnx, nx):
        graph = _weighted_twin(lib, cls_name, is_multi)
        held = _HOLD_ROUTES["getitem"](graph, "a", "b", is_multi)
        seen = []
        for weight in (1, 7, 2, 30, 4):
            seen.append(_weighted_reads(lib, graph))
            held["weight"] = weight
        seen.append(_weighted_reads(lib, graph))
        outcomes.append(seen)
    assert outcomes[0] == outcomes[1]


@pytest.mark.parametrize("cls_name", ("Graph", "DiGraph"))
def test_a_held_write_after_another_edge_is_exposed_is_seen(cls_name):
    # After a sync the next exposure re-arms a NARROW escape scope around its
    # own edge (br-r37-c1-igdzi); a dict held from before must still be checked.
    outcomes = []
    for lib in (fnx, nx):
        graph = _weighted_twin(lib, cls_name, False)
        held = graph["a"]["b"]
        first = _weighted_reads(lib, graph)
        graph["b"]["c"]  # expose another edge: the narrow scope is {b-c}
        held["weight"] = 1
        # Store-trusting readers FIRST - a kernel that syncs would rewrite the
        # whole store and hide a reader that skipped the check.
        store_reads = (graph.size(weight="weight"), sorted(graph.degree(weight="weight")))
        outcomes.append((first, store_reads, _weighted_reads(lib, graph)))
    assert outcomes[0] == outcomes[1]


@pytest.mark.parametrize("cls_name", ("Graph", "DiGraph", "MultiDiGraph"))
def test_a_value_replaced_after_a_sync_does_not_keep_the_graph_alive(cls_name):
    # The store's record of what each escaped dict held keeps the old values
    # alive until the next sync; one that refers back to the graph must not make
    # the graph uncollectable.
    import gc
    import weakref

    class Holder:
        pass

    graph = _weighted_twin(fnx, cls_name, cls_name.startswith("Multi"))
    attrs = graph["a"]["b"][0] if graph.is_multigraph() else graph["a"]["b"]
    holder = Holder()
    holder.graph = graph
    attrs["back"] = holder
    fnx.shortest_path_length(graph, "a", "c", weight="weight")  # sync + record
    attrs["back"] = None
    graph_ref = weakref.ref(graph)
    del graph, attrs, holder
    gc.collect()
    assert graph_ref() is None


# br-r37-c1-urjxk: every graph-building path hands out dicts that report their
# writes. A path that stored a plain dict would stay correct - the store is not
# trusted while an escaped dict cannot report - but every weighted call on its
# graph would re-sync the whole mirror; the token's dirty slot after a sync is
# where that shows.

from franken_networkx._fnx import dijkstra_weight_cache_token as _token  # noqa: E402


def _built(cls_name):
    graph = getattr(fnx, cls_name)()
    graph.add_weighted_edges_from([(i, (i + 1) % 10, 1.0 + i % 3) for i in range(10)] + [(0, 5, 2.5)])
    graph.add_edge(1, 7, weight=4.0, color="red")
    return graph


_BUILD_PATHS = {
    "add_edges": lambda g: g,
    "copy": lambda g: g.copy(),
    "deepcopy": lambda g: __import__("copy").deepcopy(g),
    "subgraph-copy": lambda g: g.subgraph(range(8)).copy(),
    "to_directed": lambda g: g.to_directed(),
    "class-of-graph": lambda g: type(g)(g),
    "relabel": lambda g: fnx.relabel_nodes(g, {i: i + 100 for i in range(10)}),
    "compose": lambda g: fnx.compose(g, fnx.relabel_nodes(g, {i: i + 100 for i in range(10)})),
    "disjoint_union": lambda g: fnx.disjoint_union(g, g),
}


@pytest.mark.parametrize("path", sorted(_BUILD_PATHS))
@pytest.mark.parametrize("cls_name", ("Graph", "DiGraph", "MultiDiGraph"))
def test_a_built_graph_trusts_its_store_again_after_a_sync(cls_name, path):
    graph = _BUILD_PATHS[path](_built(cls_name))
    held = [attrs for *_, attrs in graph.edges(data=True)]
    node = next(iter(graph))
    fnx.single_source_dijkstra_path_length(graph, node)
    assert _token(graph)[2] is False
    held[0]["weight"] = 9.0
    assert _token(graph)[2] is True  # the write is reported, not missed
