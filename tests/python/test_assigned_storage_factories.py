"""Dictionary factories remain live when callers supply complete graph storage."""

from collections.abc import Mapping

import networkx as nx
import pytest

import franken_networkx as fnx


GRAPH_TYPES = ("Graph", "DiGraph", "MultiGraph", "MultiDiGraph")


def _graph(lib, name):
    graph = getattr(lib, name)()
    graph._node = {}
    graph._adj = {}
    if graph.is_directed():
        graph._pred = {}
    return graph


def _plain(value):
    if isinstance(value, Mapping):
        return [(key, _plain(item)) for key, item in value.items()]
    return value


def _snapshot(graph):
    return (
        _plain(graph._node), _plain(graph._adj),
        _plain(graph._pred) if graph.is_directed() else None,
    )


def _edge_data(graph, u, v, key=0):
    data = graph._adj[u][v]
    return data[key] if graph.is_multigraph() else data


def _install_recording_factories(graph, events):
    class Attributes(dict):
        def __init__(self, kind):
            self.kind = kind
            super().__init__({"factory": kind})

        def update(self, values):
            events.append(("update", self.kind, tuple(values), tuple(graph._node)))
            super().update(values)

    class Row(dict):
        pass

    class Keys(dict):
        pass

    def attributes(kind):
        events.append(("factory", kind, tuple(graph._node), tuple(graph._adj)))
        return Attributes(kind)

    def inner():
        events.append(("factory", "row", tuple(graph._node), tuple(graph._adj)))
        return Row()

    def keys():
        events.append(("factory", "keys", tuple(graph._node), tuple(graph._adj)))
        return Keys()

    graph.node_attr_dict_factory = lambda: attributes("node")
    graph.edge_attr_dict_factory = lambda: attributes("edge")
    graph.adjlist_inner_dict_factory = inner
    if graph.is_multigraph():
        graph.edge_key_dict_factory = keys
    return Attributes, Row, Keys


@pytest.mark.parametrize("name", GRAPH_TYPES)
@pytest.mark.parametrize("operation", ["node", "nodes", "edge", "edges", "weighted"])
def test_assigned_factories_preserve_creation_and_update_order(name, operation):
    results = []
    for lib in (nx, fnx):
        graph = _graph(lib, name)
        events = []
        attributes, row_type, key_type = _install_recording_factories(graph, events)
        if operation == "node":
            graph.add_node("a", color="blue")
            original = graph._node["a"]
            graph.add_node("a", size=2)
            assert graph._node["a"] is original
        elif operation == "nodes":
            graph.add_nodes_from(["a", ("b", {"size": 2})], color="blue")
            graph.add_nodes_from([("a", {"size": 3})])
        elif operation == "edge":
            graph.add_edge("a", "b", weight=2)
            original = _edge_data(graph, "a", "b")
            if graph.is_multigraph():
                graph.add_edge("a", "b", key=0, color="blue")
            else:
                graph.add_edge("a", "b", color="blue")
            assert _edge_data(graph, "a", "b") is original
        elif operation == "edges":
            graph.add_edges_from([("a", "b", {"weight": 2}), ("b", "b")], color="blue")
        else:
            graph.add_weighted_edges_from([("a", "b", 2), ("b", "b", 3)], color="blue")
        for node, data in graph._node.items():
            assert isinstance(data, attributes)
            assert isinstance(graph._adj[node], row_type)
        if graph.is_multigraph():
            assert all(isinstance(keys, key_type) for row in graph._adj.values() for keys in row.values())
        results.append((events, _snapshot(graph)))
    assert results[0] == results[1]


@pytest.mark.parametrize("name", GRAPH_TYPES)
@pytest.mark.parametrize("where", ["instance", "class"])
def test_dynamic_factory_replacement_keeps_existing_attributes(name, where):
    class NewNode(dict):
        def __init__(self):
            super().__init__(node_default=7)

    class NewEdge(dict):
        def __init__(self):
            super().__init__(edge_default=9)

    results = []
    for lib in (nx, fnx):
        cls = type("FactoryGraph", (getattr(lib, name),), {})
        graph = cls()
        graph._node, graph._adj = {}, {}
        if graph.is_directed():
            graph._pred = {}
        graph.add_edge(0, 1)
        old_node, old_edge = graph._node[0], _edge_data(graph, 0, 1)
        owner = graph if where == "instance" else cls
        owner.node_attr_dict_factory = NewNode
        owner.edge_attr_dict_factory = NewEdge
        graph.add_node(0, updated=True)
        if graph.is_multigraph():
            graph.add_edge(0, 1, key=0, updated=True)
        else:
            graph.add_edge(0, 1, updated=True)
        graph.add_edge(1, 2)
        assert graph._node[0] is old_node
        assert _edge_data(graph, 0, 1) is old_edge
        assert type(graph._node[2]) is NewNode
        assert type(_edge_data(graph, 1, 2)) is NewEdge
        owner.node_attr_dict_factory = dict
        owner.edge_attr_dict_factory = dict
        graph.add_edge(2, 3)
        assert type(graph._node[3]) is dict
        assert type(_edge_data(graph, 2, 3)) is dict
        results.append(_snapshot(graph))
    assert results[0] == results[1]


@pytest.mark.parametrize("name", GRAPH_TYPES)
def test_shared_edge_factory_object_is_preserved(name):
    for lib in (nx, fnx):
        graph = _graph(lib, name)
        shared = {"shared": True}
        graph.edge_attr_dict_factory = lambda: shared
        graph.add_edge(0, 1, first=2)
        graph.add_edges_from([(1, 2, {"second": 3})])
        assert _edge_data(graph, 0, 1) is shared
        assert _edge_data(graph, 1, 2) is shared
        assert shared == {"shared": True, "first": 2, "second": 3}
        if graph.is_directed():
            assert graph._succ[0][1] is graph._pred[1][0]
        else:
            assert graph._adj[0][1] is graph._adj[1][0]


@pytest.mark.parametrize("name", GRAPH_TYPES)
@pytest.mark.parametrize("failure", ["first_row", "second_row", "node", "edge"])
def test_factory_failure_preserves_completed_storage_prefix(name, failure):
    results = []
    for lib in (nx, fnx):
        graph = _graph(lib, name)
        calls = {"row": 0}

        def row():
            calls["row"] += 1
            if (failure == "first_row" and calls["row"] == 1) or (
                failure == "second_row" and calls["row"] == 2
            ):
                raise RuntimeError("factory stopped")
            return {}

        def attributes(kind):
            if failure == kind:
                raise RuntimeError("factory stopped")
            return {"factory": kind}

        graph.adjlist_inner_dict_factory = row
        graph.node_attr_dict_factory = lambda: attributes("node")
        graph.edge_attr_dict_factory = lambda: attributes("edge")
        with pytest.raises(RuntimeError, match="factory stopped"):
            graph.add_edge("a", "b", weight=3)
        results.append(_snapshot(graph))
    assert results[0] == results[1]


@pytest.mark.parametrize("name", ["MultiGraph", "MultiDiGraph"])
def test_key_factory_failure_leaves_endpoints_without_an_edge(name):
    results = []
    for lib in (nx, fnx):
        graph = _graph(lib, name)

        def keys():
            raise RuntimeError("key factory stopped")

        graph.edge_key_dict_factory = keys
        with pytest.raises(RuntimeError, match="key factory stopped"):
            graph.add_edge(0, 1)
        results.append(_snapshot(graph))
    assert results[0] == results[1]
    assert results[1][0] == [(0, []), (1, [])]


@pytest.mark.parametrize("name", GRAPH_TYPES)
def test_bulk_edge_data_failure_occurs_at_the_correct_storage_stage(name):
    results = []
    for lib in (nx, fnx):
        graph = _graph(lib, name)
        observed = []

        class Data(Mapping):
            def __iter__(self):
                return iter(("first", "fail"))

            def __len__(self):
                return 2

            def __getitem__(self, key):
                observed.append((key, tuple(graph._node)))
                if key == "fail":
                    raise RuntimeError("data stopped")
                return 7

        with pytest.raises(RuntimeError, match="data stopped"):
            graph.add_edges_from([(0, 1, Data())])
        results.append((observed, _snapshot(graph)))
    assert results[0] == results[1]


@pytest.mark.parametrize("name", GRAPH_TYPES)
def test_bulk_node_membership_is_decided_before_attribute_provider(name):
    results = []
    for lib in (nx, fnx):
        graph = _graph(lib, name)
        graph.node_attr_dict_factory = lambda: {"from_factory": True}

        class Attributes(Mapping):
            def __iter__(self):
                graph._node[0] = {"from_provider": True}
                graph._adj[0] = {}
                if graph.is_directed():
                    graph._pred[0] = {}
                return iter(("x",))

            def __len__(self):
                return 1

            def __getitem__(self, key):
                return 1

        graph.add_nodes_from([(0, Attributes())])
        assert graph._node[0] == {"from_factory": True, "x": 1}
        results.append(_snapshot(graph))
    assert results[0] == results[1]


@pytest.mark.parametrize("name", GRAPH_TYPES)
def test_factory_can_replace_storage_before_assignment(name):
    results = []
    for lib in (nx, fnx):
        graph = _graph(lib, name)
        original = graph._adj
        replacement = {}
        calls = []

        def inner():
            if not calls:
                graph._adj = replacement
            calls.append(True)
            return {}

        graph.adjlist_inner_dict_factory = inner
        graph.add_edge(0, 1, weight=2)
        assert graph._adj is replacement
        assert original == {}
        results.append(_snapshot(graph))
    assert results[0] == results[1]


@pytest.mark.parametrize("name", GRAPH_TYPES)
def test_bulk_source_can_replace_storage_between_edges(name):
    results = []
    for lib in (nx, fnx):
        graph = _graph(lib, name)

        def edges():
            yield (0, 1)
            graph._node, graph._adj = {}, {}
            if graph.is_directed():
                graph._pred = {}
            yield (2, 3)

        graph.add_edges_from(edges())
        assert list(graph) == [2, 3]
        results.append(_snapshot(graph))
    assert results[0] == results[1]


@pytest.mark.parametrize("name", GRAPH_TYPES)
def test_weighted_insertion_respects_public_bulk_hook_and_clears_cache(name):
    results = []
    for lib in (nx, fnx):
        graph = _graph(lib, name)
        original = graph.add_edges_from
        events = []

        def add_edges(edges, **attributes):
            events.append("bulk")
            return original(edges, **attributes)

        graph.add_edges_from = add_edges
        graph.__networkx_cache__ = {"cached": object()}
        graph.add_weighted_edges_from([(0, 1, 2)])
        assert graph.__networkx_cache__ == {}
        results.append((events, _snapshot(graph)))
    assert results[0] == results[1]
    assert results[1][0] == ["bulk"]


@pytest.mark.parametrize("name", GRAPH_TYPES)
@pytest.mark.parametrize("route", ["numpy", "scipy"])
def test_matrix_import_populates_factory_owned_assigned_storage(name, route):
    np = pytest.importorskip("numpy")
    sparse = pytest.importorskip("scipy.sparse")

    class NodeAttributes(dict):
        def __init__(self):
            super().__init__(node_default=7)

    class EdgeAttributes(dict):
        def __init__(self):
            super().__init__(edge_default=9)

    matrix = np.array([[0, 2, 0], [0, 1, 0], [0, 0, 0]])
    results = []
    for lib in (nx, fnx):
        graph = _graph(lib, name)
        node_store, adjacency = graph._node, graph._adj
        graph.node_attr_dict_factory = NodeAttributes
        graph.edge_attr_dict_factory = EdgeAttributes
        if route == "numpy":
            result = lib.from_numpy_array(matrix, create_using=graph)
        else:
            result = lib.from_scipy_sparse_array(sparse.csr_array(matrix), create_using=graph)
        assert result is graph
        assert graph._node is node_store
        assert graph._adj is adjacency
        assert all(type(data) is NodeAttributes for data in graph._node.values())
        assert type(_edge_data(graph, 0, 1)) is EdgeAttributes
        assert type(_edge_data(graph, 1, 1)) is EdgeAttributes
        assert graph._node[2]["node_default"] == 7
        assert _edge_data(graph, 0, 1) == {"edge_default": 9, "weight": 2}
        results.append(_snapshot(graph))
    assert results[0] == results[1]
