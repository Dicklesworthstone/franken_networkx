"""Native algorithms must observe live view predicates and node data."""

import networkx as nx
import pytest

import franken_networkx as fnx


CLASSES = ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"]


def _path(lib, cls):
    graph = getattr(lib, cls)()
    graph.add_nodes_from((node, {"active": True}) for node in range(4))
    graph.add_weighted_edges_from([(0, 1, 1), (1, 2, 1), (2, 3, 1)])
    return graph


def _wrap(view, kind):
    if kind == "nested":
        return view.copy(as_view=True).copy(as_view=True)
    if kind == "conversion":
        if view.is_directed():
            return view.to_undirected(as_view=True)
        return view.to_directed(as_view=True)
    if kind == "reverse":
        return view.reverse(copy=False)
    return view


def _observe(lib, view):
    components = (
        lib.weakly_connected_components
        if view.is_directed()
        else lib.connected_components
    )
    nodes = list(view)
    return (
        nodes,
        {frozenset(part) for part in components(view)},
        dict(lib.single_source_shortest_path_length(view, 0)),
        lib.has_path(view, 0, 3),
        lib.to_numpy_array(view, nodelist=nodes).tolist(),
    )


@pytest.mark.parametrize("cls", CLASSES)
@pytest.mark.parametrize("wrapper", ["direct", "nested", "conversion", "reverse"])
@pytest.mark.parametrize("filter_kind", ["node_closure", "edge_callable"])
def test_mutable_predicates_remain_live_through_native_dispatch(cls, wrapper, filter_kind):
    if wrapper == "reverse" and cls in ("Graph", "MultiGraph"):
        pytest.skip("reverse views require a directed graph")
    results = []
    for lib in (nx, fnx):
        graph = _path(lib, cls)
        allowed = set(graph)

        class EdgeFilter:
            blocked = set()

            def __call__(self, source, target, *key):
                return frozenset((source, target)) not in self.blocked

        edge_filter = EdgeFilter()
        if filter_kind == "node_closure":
            view = lib.subgraph_view(graph, filter_node=lambda node: node in allowed)
        else:
            view = lib.subgraph_view(graph, filter_edge=edge_filter)
        view = _wrap(view, wrapper)
        sequence = [_observe(lib, view)]
        allowed.remove(1)
        edge_filter.blocked.add(frozenset((1, 2)))
        sequence.append(_observe(lib, view))
        allowed.add(1)
        edge_filter.blocked.clear()
        sequence.append(_observe(lib, view))
        results.append(sequence)
    assert results[1] == results[0]
    assert results[1][0] != results[1][1]
    assert results[1][2] == results[1][0]


@pytest.mark.parametrize("cls", CLASSES)
def test_node_filter_can_depend_on_live_node_attributes(cls):
    results = []
    for lib in (nx, fnx):
        graph = _path(lib, cls)
        view = lib.subgraph_view(
            graph, filter_node=lambda node: graph.nodes[node]["active"]
        )
        before = _observe(lib, view)
        graph.nodes[1]["active"] = False
        results.append((before, _observe(lib, view)))
    assert results[1] == results[0]


@pytest.mark.parametrize("cls", ["MultiGraph", "MultiDiGraph"])
def test_keyed_edge_filter_changes_weighted_paths(cls):
    results = []
    for lib in (nx, fnx):
        graph = _path(lib, cls)
        graph.add_edge(0, 1, key="backup", weight=8)
        blocked = set()
        view = lib.subgraph_view(
            graph,
            filter_edge=lambda u, v, key: (frozenset((u, v)), key) not in blocked,
        )
        sequence = [lib.shortest_path_length(view, 0, 3, weight="weight")]
        blocked.add((frozenset((0, 1)), 0))
        sequence.append(lib.shortest_path_length(view, 0, 3, weight="weight"))
        blocked.add((frozenset((0, 1)), "backup"))
        sequence.append(lib.has_path(view, 0, 3))
        results.append(sequence)
    assert results[1] == results[0] == [3, 10, False]


@pytest.mark.parametrize("cls", CLASSES)
def test_builtin_node_selection_cache_tracks_its_mutable_set(cls):
    graph = _path(fnx, cls)
    selection = fnx._NodeSetFilter({0, 1, 2, 3})
    view = fnx.subgraph_view(graph, filter_node=selection)
    first = fnx._materialize_view(view)
    assert fnx._materialize_view(view) is first
    selection.nodes.remove(1)
    second = fnx._materialize_view(view)
    assert second is not first
    assert list(second) == list(view) == [0, 2, 3]
    assert fnx._materialize_view(view) is second


@pytest.mark.parametrize("cls", CLASSES)
def test_unfiltered_view_chains_reuse_materialization(cls):
    graph = _path(fnx, cls)
    view = graph.copy(as_view=True)
    view = (
        view.reverse(copy=False)
        if view.is_directed()
        else view.to_directed(as_view=True)
    )
    first = fnx._materialize_view(view)
    assert fnx._materialize_view(view) is first


@pytest.mark.parametrize("cls", CLASSES)
@pytest.mark.parametrize("mutation", ["replace", "add", "delete", "clear"])
def test_union_of_a_cached_view_preserves_current_node_attributes(cls, mutation):
    results = []
    for lib in (nx, fnx):
        graph = _path(lib, cls)
        graph.nodes[1]["label"] = "before"
        view = graph.subgraph(list(graph))
        before = lib.union(view, getattr(lib, cls)())
        attrs = graph.nodes[1]
        if mutation == "replace":
            attrs["label"] = "after"
        elif mutation == "add":
            attrs["new"] = 7
        elif mutation == "delete":
            del attrs["label"]
        else:
            attrs.clear()
        after = lib.union(view, getattr(lib, cls)())
        results.append((dict(before.nodes[1]), dict(after.nodes[1])))
        assert dict(after.nodes[1]) == dict(graph.nodes[1])
    assert results[1] == results[0]
    assert results[1][0] != results[1][1]


def test_flow_demands_remain_live_after_view_conversion():
    results = []
    for lib in (nx, fnx):
        graph = lib.DiGraph()
        graph.add_node("s", demand=-1)
        graph.add_node("t", demand=1)
        graph.add_edge("s", "t", capacity=10, weight=3)
        view = graph.subgraph(["s", "t"])
        before = lib.min_cost_flow_cost(lib.union(view, lib.DiGraph()))
        graph.nodes["s"]["demand"] = -2
        graph.nodes["t"]["demand"] = 2
        after = lib.min_cost_flow_cost(lib.union(view, lib.DiGraph()))
        results.append((before, after))
    assert results[1] == results[0] == (3, 6)


@pytest.mark.parametrize("cls", CLASSES)
def test_node_attribute_snapshot_does_not_compare_user_values(cls):
    class NoEquality:
        def __eq__(self, other):
            raise AssertionError("cache validation must not compare attribute values")

    graph = _path(fnx, cls)
    value = NoEquality()
    graph.nodes[1]["opaque"] = value
    view = graph.subgraph(list(graph))
    first = fnx._materialize_view(view)
    assert first.nodes[1]["opaque"] is value
    assert fnx._materialize_view(view) is first
    replacement = NoEquality()
    graph.nodes[1]["opaque"] = replacement
    second = fnx._materialize_view(view)
    assert second is not first
    assert second.nodes[1]["opaque"] is replacement


@pytest.mark.parametrize("cls", CLASSES)
def test_node_attribute_snapshot_keeps_shallow_container_sharing(cls):
    graph = _path(fnx, cls)
    payload = {"items": []}
    graph.nodes[1]["payload"] = payload
    view = graph.subgraph(list(graph))
    first = fnx._materialize_view(view)
    payload["items"].append("new")
    assert fnx._materialize_view(view) is first
    assert first.nodes[1]["payload"] is payload
    assert first.nodes[1]["payload"]["items"] == ["new"]


def test_equal_replaced_attribute_keys_keep_the_new_identity():
    class Key:
        def __hash__(self):
            return 17

        def __eq__(self, other):
            return isinstance(other, Key)

    graph = fnx.Graph([(0, 1)])
    original_key = Key()
    graph.nodes[0][original_key] = "value"
    view = graph.subgraph([0, 1])
    first = fnx._materialize_view(view)
    del graph.nodes[0][original_key]
    replacement_key = Key()
    graph.nodes[0][replacement_key] = "value"
    second = fnx._materialize_view(view)
    assert second is not first
    assert next(iter(second.nodes[0])) is replacement_key
