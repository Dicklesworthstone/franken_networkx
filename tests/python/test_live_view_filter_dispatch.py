"""Native algorithms must observe live view predicates and node data."""

from collections import UserDict

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


@pytest.mark.parametrize("cls", CLASSES)
@pytest.mark.parametrize("wrapper", ["direct", "nested", "conversion", "reverse"])
@pytest.mark.parametrize("predicate_kind", ["truthiness", "comparison"])
def test_closure_free_node_predicates_keep_live_python_protocols(
    cls, wrapper, predicate_kind
):
    if wrapper == "reverse" and cls in ("Graph", "MultiGraph"):
        pytest.skip("reverse views require a directed graph")

    class Node:
        def __init__(self, label):
            self.label = label
            self.visible = True

        def __bool__(self):
            return self.visible

        def __gt__(self, other):
            return self.visible

    nodes = [Node(label) for label in range(4)]
    predicate = (
        (lambda node: node)
        if predicate_kind == "truthiness"
        else (lambda node: node > 0)
    )
    # Neither callback mentions globals or captures closure/default state, but
    # both invoke a mutable node protocol when the view tests membership.
    assert not predicate.__code__.co_names
    assert predicate.__closure__ is None

    graphs = [getattr(lib, cls)() for lib in (nx, fnx)]
    for graph in graphs:
        graph.add_nodes_from(nodes)
        graph.add_edges_from(zip(nodes, nodes[1:]))
    expected, actual = (
        _wrap(lib.subgraph_view(graph, filter_node=predicate), wrapper)
        for lib, graph in zip((nx, fnx), graphs)
    )

    for visible in (True, False, True):
        nodes[1].visible = visible
        snapshot = fnx._materialize_view(actual)
        assert list(snapshot) == list(actual) == list(expected)
        nx_components = (
            nx.weakly_connected_components
            if expected.is_directed()
            else nx.connected_components
        )
        fnx_components = (
            fnx.weakly_connected_components
            if actual.is_directed()
            else fnx.connected_components
        )
        assert {frozenset(part) for part in fnx_components(actual)} == {
            frozenset(part) for part in nx_components(expected)
        }


@pytest.mark.parametrize("cls", CLASSES)
@pytest.mark.parametrize("wrapper", ["direct", "nested", "conversion", "reverse"])
def test_cached_view_tracks_replacement_graph_attribute_mapping(cls, wrapper):
    if wrapper == "reverse" and cls in ("Graph", "MultiGraph"):
        pytest.skip("reverse views require a directed graph")

    expected_graph, actual_graph = (_path(lib, cls) for lib in (nx, fnx))
    expected_graph.graph["phase"] = actual_graph.graph["phase"] = "before"
    expected = _wrap(expected_graph.subgraph(list(expected_graph)), wrapper)
    actual = _wrap(actual_graph.subgraph(list(actual_graph)), wrapper)
    first = fnx._materialize_view(actual)
    assert first.graph is actual.graph

    payload = []
    for view in (expected, actual):
        # Graph assignment preserves ordinary dictionary identity in fnx.
        # A general mapping is replaced, so sharing the previous dictionary
        # cannot make a previously materialized view observe this assignment.
        view.graph = UserDict({"phase": "after", "payload": payload})
    second = fnx._materialize_view(actual)
    assert second.graph is actual.graph
    assert dict(second.graph) == dict(expected.graph)
    assert second.graph["payload"] is payload

    for name in ("union", "compose"):
        nx_result = getattr(nx, name)(expected, type(expected)())
        fnx_result = getattr(fnx, name)(actual, getattr(fnx, type(expected).__name__)())
        assert dict(fnx_result.graph) == dict(nx_result.graph)
        assert fnx_result.graph["payload"] is payload


@pytest.mark.parametrize("cls", CLASSES)
@pytest.mark.parametrize("mapping_type", [dict, UserDict])
def test_conversion_view_graph_mapping_assignment_keeps_local_ownership(cls, mapping_type):
    for lib in (nx, fnx):
        graph = _path(lib, cls)
        graph.graph["phase"] = "shared"
        view = (
            graph.to_undirected(as_view=True)
            if graph.is_directed()
            else graph.to_directed(as_view=True)
        )
        shared = graph.graph
        assert view.graph is shared
        shared["updated"] = True
        assert view.graph["updated"] is True

        graph.graph = UserDict({"phase": "parent"})
        assert view.graph is shared
        assert view.graph["phase"] == "shared"

        payload = []
        replacement = mapping_type({"phase": "view", "payload": payload})
        view.graph = replacement
        assert view.graph is replacement
        assert graph.graph == {"phase": "parent"}
        assert shared == {"phase": "shared", "updated": True}
        assert view.graph["payload"] is payload


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
@pytest.mark.parametrize("custom_key_location", ["selection", "graph"])
def test_node_set_filter_membership_protocol_stays_live(cls, custom_key_location):
    class Alias:
        enabled = True

        def __hash__(self):
            return hash("selected")

        def __eq__(self, other):
            return other is self or (
                self.enabled and type(other) is str and other == "selected"
            )

    alias = Alias()
    node = "selected" if custom_key_location == "selection" else alias
    selected = {alias if custom_key_location == "selection" else "selected", "neighbor"}
    expected_graph, actual_graph = (getattr(lib, cls)() for lib in (nx, fnx))
    for graph in (expected_graph, actual_graph):
        graph.add_edge(node, "neighbor")
    expected = nx.subgraph_view(expected_graph, filter_node=nx.filters.show_nodes(selected))
    actual = fnx.subgraph_view(actual_graph, filter_node=fnx._NodeSetFilter(selected))

    for enabled in (True, False, True):
        alias.enabled = enabled
        assert list(fnx._materialize_view(actual)) == list(actual) == list(expected)


@pytest.mark.parametrize("cls", CLASSES)
def test_builtin_container_node_keys_keep_view_cache_reuse(cls):
    nodes = [("left", 1), frozenset({"right", 2})]
    graph = getattr(fnx, cls)()
    graph.add_edge(*nodes)
    view = fnx.subgraph_view(graph, filter_node=fnx._NodeSetFilter(set(nodes)))
    first = fnx._materialize_view(view)
    assert fnx._materialize_view(view) is first


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
