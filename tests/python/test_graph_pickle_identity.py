"""Pickle preserves the graph's object relationships, not only its values."""

import copy
import pickle
from collections import UserDict

import networkx as nx
import pytest

import franken_networkx as fnx


_CLASSES = ("Graph", "DiGraph", "MultiGraph", "MultiDiGraph")
_PROTOCOLS = range(pickle.HIGHEST_PROTOCOL + 1)


def _round_trip(value, protocol):
    return pickle.loads(pickle.dumps(value, protocol=protocol))


def _edge_data(graph):
    return graph[0][1][0] if graph.is_multigraph() else graph[0][1]


def _attribute_layers(graph):
    return graph.graph, graph.nodes[0], _edge_data(graph), vars(graph)


@pytest.mark.parametrize("name", _CLASSES)
@pytest.mark.parametrize("protocol", _PROTOCOLS)
def test_pickle_graph_backrefs_self_cycles_and_cross_layer_aliases(name, protocol):
    for module in (nx, fnx):
        graph = getattr(module, name)([(0, 1)])
        graph_data, node_data, edge_data, instance = _attribute_layers(graph)
        payload = []
        for data in (graph_data, node_data, edge_data, instance):
            data["owner"] = graph
            data["payload"] = payload
        for data in (graph_data, node_data, edge_data):
            data["self"] = data
            data["graph_data"] = graph_data
            data["node_data"] = node_data
            data["edge_data"] = edge_data

        restored = _round_trip(graph, protocol)
        restored_layers = _attribute_layers(restored)
        for data in restored_layers:
            assert data["owner"] is restored
            assert data["payload"] is restored.graph["payload"]
        for data in restored_layers[:3]:
            assert data["self"] is data
            assert data["graph_data"] is restored.graph
            assert data["node_data"] is restored.nodes[0]
            assert data["edge_data"] is _edge_data(restored)
        restored.graph["payload"].append("changed")
        assert payload == []
        assert graph_data["owner"] is graph


@pytest.mark.parametrize("name", _CLASSES)
@pytest.mark.parametrize("protocol", _PROTOCOLS)
@pytest.mark.parametrize("graph_first", (True, False))
def test_pickle_external_attribute_dictionary_identity(name, protocol, graph_first):
    # Even an empty dictionary may have aliases outside the graph. Native
    # rebuilding cannot decide that copying an apparently simple dict is safe.
    for module in (nx, fnx):
        graph = getattr(module, name)([(0, 1)])
        objects = [graph, graph.nodes[0], _edge_data(graph), graph.graph]
        if not graph_first:
            objects.reverse()
        restored = _round_trip(objects, protocol)
        if not graph_first:
            restored.reverse()
        copied, node_data, edge_data, graph_data = restored
        assert copied.nodes[0] is node_data
        assert _edge_data(copied) is edge_data
        assert copied.graph is graph_data
        node_data["color"] = "green"
        edge_data["weight"] = 3
        graph_data["name"] = "restored"
        assert copied.nodes[0]["color"] == "green"
        assert _edge_data(copied)["weight"] == 3
        assert copied.name == "restored"
        assert "color" not in graph.nodes[0]
        assert "weight" not in _edge_data(graph)


@pytest.mark.parametrize("name", _CLASSES)
@pytest.mark.parametrize("protocol", _PROTOCOLS)
def test_pickle_mutually_referring_graphs_and_repeated_graph(name, protocol):
    for module in (nx, fnx):
        first = getattr(module, name)([(0, 1)])
        second = getattr(module, name)([(0, 1)])
        first.graph["peer"] = second
        second.nodes[0]["peer"] = first
        _edge_data(second)["first_edge"] = _edge_data(first)
        copied_first, copied_second, repeated = _round_trip(
            [first, second, first], protocol
        )
        assert copied_first is repeated
        assert copied_first.graph["peer"] is copied_second
        assert copied_second.nodes[0]["peer"] is copied_first
        assert _edge_data(copied_second)["first_edge"] is _edge_data(copied_first)


@pytest.mark.parametrize("name", ("MultiGraph", "MultiDiGraph"))
@pytest.mark.parametrize("protocol", _PROTOCOLS)
@pytest.mark.parametrize("graph_first", (True, False))
def test_pickle_multiedge_dictionary_cycles_and_outer_aliases(name, protocol, graph_first):
    for module in (nx, fnx):
        graph = getattr(module, name)([(0, 1)])
        keydict = graph._adj[0][1]
        keydict[0]["keys"] = keydict
        graph.graph["keys"] = keydict
        objects = [graph, keydict] if graph_first else [keydict, graph]
        restored = _round_trip(objects, protocol)
        copied, copied_keys = restored if graph_first else reversed(restored)
        assert copied._adj[0][1] is copied_keys
        assert copied.graph["keys"] is copied_keys
        assert copied_keys[0]["keys"] is copied_keys
        assert copied._adj[0][1] is (
            copied._pred[1][0] if copied.is_directed() else copied._adj[1][0]
        )
        copied.add_edge(0, 1, key="new")
        assert list(copied_keys) == [0, "new"]
        assert list(keydict) == [0]


@pytest.mark.parametrize("name", _CLASSES)
@pytest.mark.parametrize("protocol", (2, pickle.HIGHEST_PROTOCOL))
def test_pickle_after_deepcopy_keeps_live_metadata_and_mutation(name, protocol):
    for module in (nx, fnx):
        original = getattr(module, name)([(0, 1)])
        original.graph["metadata"] = {"version": 1}
        _edge_data(original)["weight"] = 7
        graph = copy.deepcopy(original)
        graph.graph["metadata"]["version"] = 2
        graph.graph["owner"] = graph
        graph.add_edge(1, 2, weight=3)
        restored = _round_trip(graph, protocol)
        assert restored.graph["metadata"] == {"version": 2}
        assert restored.graph["owner"] is restored
        assert list(restored) == [0, 1, 2]
        assert module.dijkstra_path_length(restored, 0, 2) == 10
        restored.add_edge(2, 3, weight=1)
        restored.remove_edge(0, 1)
        assert list(restored.edges()) == [(1, 2), (2, 3)]
        assert original.graph["metadata"] == {"version": 1}
        assert list(original.edges()) == [(0, 1)]
        assert _round_trip(restored, protocol).graph["metadata"] == {"version": 2}


class _PickleDict(dict):
    """A user mapping with its own instance state."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.marker = "user storage"


def _with_assigned_storage(module, name, mapping_class):
    graph = getattr(module, name)()
    node_data = mapping_class(label="first")
    edge_data = mapping_class(weight=2)
    graph.graph = mapping_class(name="custom")
    graph._node = mapping_class({0: node_data, 1: mapping_class()})
    adjacent = mapping_class({0: edge_data}) if graph.is_multigraph() else edge_data
    adjacency = mapping_class({0: mapping_class({1: adjacent}), 1: mapping_class()})
    if graph.is_directed():
        graph._succ = adjacency
        graph._pred = mapping_class(
            {0: mapping_class(), 1: mapping_class({0: adjacent})}
        )
    else:
        adjacency[1][0] = adjacent
    graph._adj = adjacency
    graph.graph["nodes"] = graph._node
    graph.graph["adjacency"] = graph._adj
    graph.graph["edge_data"] = edge_data
    return graph


@pytest.mark.parametrize("name", _CLASSES)
@pytest.mark.parametrize("mapping_class", (_PickleDict, UserDict))
@pytest.mark.parametrize("protocol", (2, pickle.HIGHEST_PROTOCOL))
def test_pickle_custom_logical_storage_types_and_sharing(name, mapping_class, protocol):
    for module in (nx, fnx):
        graph = _with_assigned_storage(module, name, mapping_class)
        restored = _round_trip(graph, protocol)
        assert type(restored._node) is mapping_class
        assert type(restored._adj) is mapping_class
        assert type(restored.graph) is type(graph.graph)
        assert type(restored.nodes[0]) is mapping_class
        assert type(_edge_data(restored)) is mapping_class
        assert restored.graph["nodes"] is restored._node
        assert restored.graph["adjacency"] is restored._adj
        assert restored.graph["edge_data"] is _edge_data(restored)
        if mapping_class is _PickleDict:
            assert restored._node.marker == "user storage"
            assert _edge_data(restored).marker == "user storage"
        if restored.is_directed():
            assert restored._succ is restored._adj
            assert restored._succ[0][1] is restored._pred[1][0]
        else:
            assert restored._adj[0][1] is restored._adj[1][0]
        restored.add_edge(1, 2)
        assert list(restored) == [0, 1, 2]
        assert list(graph) == [0, 1]


def _make_required_init_subclass(module, name):
    base = getattr(module, name)
    class_name = f"_{module.__name__}_{name}_RequiredInit"

    def initialize(self, payload):
        base.__init__(self)
        type(self).initializations += 1
        self.payload = payload
        self.slot_payload = payload
        setattr(self, f"_{class_name.lstrip('_')}__private_payload", payload)

    cls = type(
        class_name,
        (base,),
        {
            "__module__": __name__,
            "__slots__": ("slot_payload", "__private_payload", "unassigned"),
            "__init__": initialize,
            "initializations": 0,
            "graph_attr_dict_factory": _PickleDict,
        },
    )
    globals()[class_name] = cls
    return cls


_SUBCLASSES = {
    (module.__name__, name): _make_required_init_subclass(module, name)
    for module in (nx, fnx)
    for name in _CLASSES
}


@pytest.mark.parametrize("name", _CLASSES)
@pytest.mark.parametrize("protocol", (2, pickle.HIGHEST_PROTOCOL))
def test_pickle_subclass_slots_factories_without_reinitializing(name, protocol):
    for module in (nx, fnx):
        cls = _SUBCLASSES[module.__name__, name]
        graph = cls([])
        graph.add_edge(0, 1)
        graph.graph["payload"] = graph.payload
        graph.nodes[0]["payload"] = graph.payload
        initializations = cls.initializations
        restored = _round_trip(graph, protocol)
        assert type(restored) is cls
        assert cls.initializations == initializations
        assert type(restored.graph) is _PickleDict
        assert restored.payload is restored.slot_payload
        assert restored.payload is getattr(
            restored, f"_{cls.__name__.lstrip('_')}__private_payload"
        )
        assert restored.payload is restored.graph["payload"]
        assert restored.payload is restored.nodes[0]["payload"]
        assert restored.payload is not graph.payload
        assert not hasattr(restored, "unassigned")


class _PickleLabel:
    pass


@pytest.mark.parametrize("name", _CLASSES)
@pytest.mark.parametrize("protocol", (2, pickle.HIGHEST_PROTOCOL))
def test_pickle_node_and_multiedge_key_object_identity(name, protocol):
    for module in (nx, fnx):
        graph = getattr(module, name)()
        node, key = _PickleLabel(), _PickleLabel()
        if graph.is_multigraph():
            graph.add_edge(node, 1, key=key)
        else:
            graph.add_edge(node, 1)
        graph.graph.update(node=node, key=key)
        graph.nodes[node]["label"] = node
        restored, restored_node, restored_key = _round_trip([graph, node, key], protocol)
        assert next(iter(restored)) is restored_node
        assert restored.graph["node"] is restored_node
        assert restored.nodes[restored_node]["label"] is restored_node
        assert restored.graph["key"] is restored_key
        if restored.is_multigraph():
            assert next(iter(restored[restored_node][1])) is restored_key


_PICKLE_VIEW_CASES = [
    (name, kind)
    for name in _CLASSES
    for kind in ("subgraph", "edge_subgraph", "copy", "directed", "undirected", "nested")
] + [(name, "reverse") for name in ("DiGraph", "MultiDiGraph")]


def _pickle_snapshot_view(graph, kind):
    if kind == "subgraph":
        return graph.subgraph(list(graph)[:3])
    if kind == "edge_subgraph":
        return graph.edge_subgraph(list(graph.edges)[:2])
    if kind == "copy":
        return graph.copy(as_view=True)
    if kind == "directed":
        return graph.to_directed(as_view=True)
    if kind == "undirected":
        return graph.to_undirected(as_view=True)
    if kind == "nested":
        return graph.subgraph(list(graph)[:3]).to_directed(as_view=True).reverse(copy=False)
    return graph.reverse(copy=False)


def _pickle_view_layers(graph):
    node = next(iter(graph))
    edge = next(iter(graph.edges))
    attrs = graph[edge[0]][edge[1]]
    if graph.is_multigraph():
        attrs = attrs[edge[2]]
    return graph.graph, graph.nodes[node], attrs


@pytest.mark.parametrize("name,kind", _PICKLE_VIEW_CASES)
@pytest.mark.parametrize("protocol", _PROTOCOLS)
def test_pickle_view_snapshot_preserves_recursive_attributes(name, kind, protocol):
    graph = getattr(fnx, name)([(0, 1), (1, 2), (2, 0), (3, 3)])
    view = _pickle_snapshot_view(graph, kind)
    layers = _pickle_view_layers(view)
    payload = []
    for attrs in layers:
        attrs.update(owner=view, payload=payload)
        attrs["self"] = attrs
        attrs["graph_data"], attrs["node_data"], attrs["edge_data"] = layers
    # Read logical iteration order without an edge-count length hint, which
    # may independently materialize a nested conversion view.
    nodes, edges = list(view), [edge for edge in view.edges]

    restored = _round_trip(view, protocol)
    restored_layers = _pickle_view_layers(restored)
    assert list(restored) == nodes
    assert list(restored.edges) == edges
    assert fnx.is_frozen(restored)
    for attrs in restored_layers:
        assert attrs["owner"] is restored
        assert attrs["self"] is attrs
        assert attrs["payload"] is restored.graph["payload"]
        for label, expected in zip(("graph_data", "node_data", "edge_data"), restored_layers):
            assert attrs[label] is expected
    restored.graph["payload"].append("restored only")
    assert payload == []
    graph.add_node(99)
    assert 99 not in restored
    with pytest.raises(fnx.NetworkXError, match="Frozen graph"):
        restored.add_node(100)


@pytest.mark.parametrize("name,kind", _PICKLE_VIEW_CASES)
@pytest.mark.parametrize("protocol", (2, pickle.HIGHEST_PROTOCOL))
@pytest.mark.parametrize("view_first", (False, True))
def test_pickle_view_snapshot_keeps_outer_dictionary_aliases(name, kind, protocol, view_first):
    graph = getattr(fnx, name)([(0, 1), (1, 2), (2, 0)])
    view = _pickle_snapshot_view(graph, kind)
    layers = _pickle_view_layers(view)
    objects = [view, *layers] if view_first else [*layers, view]
    restored = _round_trip(objects, protocol)
    copied = restored[0] if view_first else restored[-1]
    copied_layers = restored[1:] if view_first else restored[:-1]
    for actual, expected in zip(_pickle_view_layers(copied), copied_layers):
        assert actual is expected
    copied_layers[1]["color"] = "green"
    copied_layers[2]["weight"] = 7
    assert "color" not in layers[1]
    assert "weight" not in layers[2]


@pytest.mark.parametrize("name,kind", _PICKLE_VIEW_CASES)
def test_pickle_view_snapshot_remaps_nodes_and_parallel_keys(name, kind):
    graph = getattr(fnx, name)()
    node, key = _PickleLabel(), _PickleLabel()
    if graph.is_multigraph():
        graph.add_edge(node, "target", key=key, label=key)
    else:
        graph.add_edge(node, "target", label=key)
    view = _pickle_snapshot_view(graph, kind)
    view.graph.update(owner=view, node=node, key=key)
    view.nodes[node]["label"] = node
    restored, copied_node, copied_key = _round_trip(
        [view, node, key], pickle.HIGHEST_PROTOCOL
    )
    assert restored.graph["owner"] is restored
    assert next(iter(restored)) is copied_node
    assert restored.graph["node"] is copied_node
    assert restored.nodes[copied_node]["label"] is copied_node
    assert restored.graph["key"] is copied_key
    edge = next(iter(restored.edges))
    data = restored[edge[0]][edge[1]]
    if restored.is_multigraph():
        assert edge[2] is copied_key
        data = data[copied_key]
    assert data["label"] is copied_key


@pytest.mark.parametrize("name,kind", [
    (name, kind) for name, kind in _PICKLE_VIEW_CASES
    if name in ("MultiGraph", "MultiDiGraph")
])
def test_pickle_view_snapshot_keeps_shared_parallel_key_dictionaries(name, kind):
    graph = getattr(fnx, name)()
    graph.add_edges_from([(0, 1, "first"), (0, 1, "second"), (1, 2, "last")])
    restored = _round_trip(_pickle_snapshot_view(graph, kind), pickle.HIGHEST_PROTOCOL)
    opposite = restored._pred if restored.is_directed() else restored._adj
    for node, row in restored._adj.items():
        for neighbor, keys in row.items():
            assert keys is opposite[neighbor][node]


@pytest.mark.parametrize("name", _CLASSES)
def test_pickle_view_snapshot_excludes_hidden_unpicklable_data(name):
    graph = getattr(fnx, name)([(0, 1), (1, 2)])
    graph.nodes[2]["hidden"] = _Unpicklable()
    view = fnx.subgraph_view(graph, filter_node=lambda node: node < 2)
    restored = _round_trip(view, pickle.HIGHEST_PROTOCOL)
    assert list(restored) == [0, 1]
    assert list(restored.edges()) == [(0, 1)]
    view.nodes[0]["visible"] = _Unpicklable()
    with pytest.raises(ValueError, match="^cannot serialize payload$"):
        pickle.dumps(view)


@pytest.mark.parametrize("name", ("DiGraph", "MultiDiGraph"))
def test_pickle_view_snapshot_keeps_distinct_reciprocal_attributes(name):
    graph = getattr(fnx, name)()
    graph.add_edge(0, 1, direction="forward", payload=[])
    graph.add_edge(1, 0, direction="backward", payload=[])
    view = graph.to_undirected(as_view=True)
    view.graph["owner"] = view
    restored = _round_trip(view, pickle.HIGHEST_PROTOCOL)
    forward, backward = restored[0][1], restored[1][0]
    if restored.is_multigraph():
        forward, backward = forward[0], backward[0]
    assert forward["direction"] == "forward"
    assert backward["direction"] == "backward"
    assert forward is not backward
    assert forward["payload"] is not backward["payload"]
    assert restored.graph["owner"] is restored


@pytest.mark.parametrize("name", ("DiGraph", "MultiDiGraph"))
def test_pickle_view_snapshot_reverse_preserves_parent_class_without_init(name):
    cls = _SUBCLASSES[fnx.__name__, name]
    graph = cls([])
    graph.add_edge(0, 1)
    view = graph.reverse(copy=False)
    view.graph["owner"] = view
    initializations = cls.initializations
    restored = _round_trip(view, pickle.HIGHEST_PROTOCOL)
    assert type(restored) is cls
    assert cls.initializations == initializations
    assert restored.graph["owner"] is restored
    assert list(restored.edges()) == [(1, 0)]
    assert fnx.is_frozen(restored)


def _custom_frozen_override(*args, **kwargs):
    return "custom"


@pytest.mark.parametrize("name", _CLASSES)
@pytest.mark.parametrize("protocol", (2, pickle.HIGHEST_PROTOCOL))
def test_pickle_frozen_status_and_user_override(name, protocol):
    for module in (nx, fnx):
        graph = getattr(module, name)([(0, 1)])
        graph.graph["owner"] = graph
        module.freeze(graph)
        graph.add_node = _custom_frozen_override
        restored = _round_trip(graph, protocol)
        assert module.is_frozen(restored)
        assert restored.graph["owner"] is restored
        assert restored.add_node(2) == "custom"
        with pytest.raises(nx.NetworkXError, match="Frozen graph"):
            restored.add_edge(1, 2)
        assert list(restored) == [0, 1]


class _Unpicklable:
    def __reduce__(self):
        raise ValueError("cannot serialize payload")


@pytest.mark.parametrize("name", _CLASSES)
@pytest.mark.parametrize("layer", range(4))
def test_pickle_propagates_user_serialization_errors(name, layer):
    for module in (nx, fnx):
        graph = getattr(module, name)([(0, 1)])
        _attribute_layers(graph)[layer]["payload"] = _Unpicklable()
        with pytest.raises(ValueError, match="^cannot serialize payload$"):
            pickle.dumps(graph)


@pytest.mark.parametrize("name", _CLASSES)
@pytest.mark.parametrize("mode", ("strict", "hardened"))
def test_pickle_retains_native_compatibility_policy(name, mode):
    with fnx.compatibility_mode(mode):
        graph = getattr(fnx, name)([(0, 1)])
    before = graph.__getstate__()
    restored = _round_trip(graph, pickle.HIGHEST_PROTOCOL)
    after = restored.__getstate__()
    assert after["mode"] == before["mode"] == mode
    assert after["runtime_policy"] == before["runtime_policy"]
    assert list(restored.edges()) == [(0, 1)]


def _graph_and_view_round_trip(graph, view, protocol, order):
    if order == "cycle":
        graph.graph["held"] = view
        restored = _round_trip(graph, protocol)
        return restored, restored.graph["held"]
    objects = [graph, view] if order == "graph_first" else [view, graph]
    restored = _round_trip(objects, protocol)
    return restored if order == "graph_first" else restored[::-1]


def _weighted_view_graph(module, name):
    graph = getattr(module, name)()
    graph.add_nodes_from(range(4))
    graph.add_edge(0, 1, weight=2)
    graph.add_edge(1, 2, weight=3)
    graph.add_edge(1, 1, weight=5)
    if graph.is_multigraph():
        graph.add_edge(0, 1, weight=7)
    return graph


@pytest.mark.parametrize("name", ("DiGraph", "MultiGraph", "MultiDiGraph"))
@pytest.mark.parametrize("protocol", (2, pickle.HIGHEST_PROTOCOL))
@pytest.mark.parametrize("order", ("graph_first", "view_first", "cycle"))
def test_pickle_edge_view_keeps_restored_owner_and_live_readers(name, protocol, order):
    observations = []
    for module in (nx, fnx):
        graph = _weighted_view_graph(module, name)
        restored, view = _graph_and_view_round_trip(graph, graph.edges, protocol, order)
        assert view._graph is restored
        before = list(view)
        restored.add_edge(2, 3, weight=11)
        _edge_data(restored)["weight"] = 13
        edge = (0, 1, 0) if restored.is_multigraph() else (0, 1)
        assert view[edge] is _edge_data(restored)
        assert view[edge]["weight"] == 13
        options = {"data": "weight"}
        if restored.is_multigraph():
            options["keys"] = True
        after = (list(view), list(view(**options)), len(view))
        repeated_graph, repeated_view = _round_trip([restored, view], protocol)
        assert repeated_view._graph is repeated_graph
        assert list(repeated_view) == list(view)
        assert _edge_data(graph)["weight"] == 2
        assert not graph.has_edge(2, 3)
        observations.append((before, after))
    assert observations[0] == observations[1]


_DEGREE_VIEWS = (
    ("MultiGraph", "degree"),
    ("MultiDiGraph", "degree"),
    ("DiGraph", "in_degree"),
    ("DiGraph", "out_degree"),
    ("MultiDiGraph", "in_degree"),
    ("MultiDiGraph", "out_degree"),
)


@pytest.mark.parametrize("name, accessor", _DEGREE_VIEWS)
@pytest.mark.parametrize("configuration", ("bare", "weighted", "subset"))
@pytest.mark.parametrize("protocol", (2, pickle.HIGHEST_PROTOCOL))
@pytest.mark.parametrize("order", ("graph_first", "view_first", "cycle"))
def test_pickle_degree_view_keeps_direction_weight_subset_and_owner(
    name, accessor, configuration, protocol, order
):
    observations = []
    for module in (nx, fnx):
        graph = _weighted_view_graph(module, name)
        view = getattr(graph, accessor)
        if configuration == "weighted":
            view = view(weight="weight")
        elif configuration == "subset":
            view = view([0, 2], weight="weight")
        restored, view = _graph_and_view_round_trip(graph, view, protocol, order)
        assert view._graph is restored
        before = (list(view), view[0], len(view))
        restored.add_edge(2, 3, weight=11)
        _edge_data(restored)["weight"] = 13
        after = (list(view), view[0], len(view), list(view([0, 1], weight="weight")))
        repeated_graph, repeated_view = _round_trip([restored, view], protocol)
        assert repeated_view._graph is repeated_graph
        assert list(repeated_view) == list(view)
        assert repeated_view[0] == view[0]
        assert _edge_data(graph)["weight"] == 2
        assert not graph.has_edge(2, 3)
        observations.append((before, after))
    assert observations[0] == observations[1]
