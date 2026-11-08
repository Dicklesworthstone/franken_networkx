"""Byte-exact + deep-semantics conformance guard for graph __deepcopy__.

The remaining construction-tax lever (br-r37-c1-n7gxs #2) would fold the deepcopy
paths (__deepcopy__, _native_to_directed_deepcopy) with a single-pass
deepcopy+AttrMap helper. That fold is NOT correct-by-construction — per-value
deepcopy differs from whole-dict deepcopy in memo sharing of nested objects — so
it needs this guard to land safely. This locks the deep semantics vs networkx:

  * deepcopy(G) reproduces node/edge/graph attrs exactly (values match nx);
  * source-independence: mutating the source after deepcopy leaves the copy
    unchanged (top-level);
  * DEEP independence: mutating a NESTED mutable attr (a list/dict inside an
    attr) in the source does NOT change the copy — this is what distinguishes
    deepcopy from a shallow copy, and what the fold must preserve.

No mocks: real fnx vs real networkx (copy.deepcopy).
"""

from __future__ import annotations

import copy
import random

import pytest
import networkx as nx
import franken_networkx as fnx

_TYPES = [
    (fnx.Graph, nx.Graph),
    (fnx.DiGraph, nx.DiGraph),
    (fnx.MultiGraph, nx.MultiGraph),
    (fnx.MultiDiGraph, nx.MultiDiGraph),
]


def _build(fcls, ncls, seed):
    r = random.Random(seed)
    n = r.randint(4, 8)
    fg, ng = fcls(), ncls()
    for node in range(n):
        # Include a NESTED mutable attr to exercise deep semantics.
        fg.add_node(node, tag=f"t{node}", items=[node, node + 1])
        ng.add_node(node, tag=f"t{node}", items=[node, node + 1])
    directed = fg.is_directed()
    for u in range(n):
        for v in range(n):
            if (u < v or (directed and u != v)) and r.random() < 0.4:
                w = r.randint(1, 9)  # local: G[u][v]["weight"] is invalid on MultiGraph
                fg.add_edge(u, v, weight=w, meta={"k": u})
                ng.add_edge(u, v, weight=w, meta={"k": u})
    fg.graph["info"] = {"name": "g"}
    ng.graph["info"] = {"name": "g"}
    return fg, ng, n


def _node_attrs(g):
    return {n: dict(d) for n, d in g.nodes(data=True)}


@pytest.mark.parametrize("fcls,ncls", _TYPES)
@pytest.mark.parametrize("seed", range(12))
def test_deepcopy_attrs_match_networkx(fcls, ncls, seed):
    fg, ng, n = _build(fcls, ncls, seed)
    fc, nc = copy.deepcopy(fg), copy.deepcopy(ng)
    assert _node_attrs(fc) == _node_attrs(nc)
    assert dict(fc.graph) == dict(nc.graph)


@pytest.mark.parametrize("fcls,ncls", _TYPES)
@pytest.mark.parametrize("seed", range(12))
def test_deepcopy_is_deeply_independent(fcls, ncls, seed):
    fg, ng, n = _build(fcls, ncls, seed)
    fc = copy.deepcopy(fg)
    before = _node_attrs(fc)
    # Mutate a NESTED attr in the source; a true deepcopy is unaffected.
    for node in list(fg.nodes()):
        fg.nodes[node]["items"].append(999)
        fg.nodes[node]["tag"] = "MUT"
        break
    fg.graph["info"]["name"] = "MUT"
    assert _node_attrs(fc) == before          # nested list + tag unchanged
    assert fc.graph["info"]["name"] == "g"     # nested graph attr unchanged


@pytest.mark.parametrize("fcls,ncls", [(fnx.Graph, nx.Graph), (fnx.MultiGraph, nx.MultiGraph)])
def test_to_directed_deepcopy_preserves_in_dict_aliasing(fcls, ncls):
    """A per-value deepcopy would incorrectly duplicate this shared list."""
    fg, ng = fcls(), ncls()
    shared_values = []
    for graph in (fg, ng):
        shared = ["source"]
        shared_values.append(shared)
        graph.add_node("u", first=shared, second=shared)
        graph.add_edge("u", "v", first=shared, second=shared)

    fc, nc = fg.to_directed(), ng.to_directed()
    for converted, source_shared in zip((fc, nc), shared_values, strict=True):
        node_attrs = converted.nodes["u"]
        edge_attrs = (
            converted["u"]["v"][0] if converted.is_multigraph() else converted["u"]["v"]
        )
        assert node_attrs["first"] is node_attrs["second"]
        assert edge_attrs["first"] is edge_attrs["second"]
        assert node_attrs["first"] is not source_shared
        assert edge_attrs["first"] is not source_shared


def _edge_attrs(graph):
    return graph[0][1][0] if graph.is_multigraph() else graph[0][1]


def _attribute_layer(graph, layer):
    if layer == "graph":
        return graph.graph
    if layer == "node":
        return graph.nodes[0]
    if layer == "edge":
        return _edge_attrs(graph)
    return vars(graph)


@pytest.mark.parametrize("fcls,ncls", _TYPES)
@pytest.mark.parametrize("layer", ["graph", "node", "edge", "instance"])
def test_deepcopy_graph_backreferences_use_the_copy(fcls, ncls, layer):
    for cls in (ncls, fcls):
        graph = cls([(0, 1)])
        _attribute_layer(graph, layer)["owner"] = graph
        copied = copy.deepcopy(graph)
        assert copied is not graph
        assert _attribute_layer(copied, layer)["owner"] is copied


@pytest.mark.parametrize("fcls,ncls", _TYPES)
@pytest.mark.parametrize("layer", ["graph", "node", "edge"])
def test_deepcopy_attribute_dictionary_cycles(fcls, ncls, layer):
    for cls in (ncls, fcls):
        graph = cls([(0, 1)])
        attrs = _attribute_layer(graph, layer)
        attrs["self"] = attrs
        copied = copy.deepcopy(graph)
        copied_attrs = _attribute_layer(copied, layer)
        assert copied_attrs is not attrs
        assert copied_attrs["self"] is copied_attrs


@pytest.mark.parametrize("fcls,ncls", _TYPES)
def test_deepcopy_preserves_aliases_between_all_attribute_layers(fcls, ncls):
    for cls in (ncls, fcls):
        graph = cls([(0, 1)])
        node_attrs = graph.nodes[0]
        edge_attrs = _edge_attrs(graph)
        graph.graph["node"] = node_attrs
        node_attrs["edge"] = edge_attrs
        edge_attrs["graph"] = graph.graph
        graph.payload = [node_attrs, edge_attrs, graph.graph]
        copied = copy.deepcopy(graph)
        assert copied.graph["node"] is copied.nodes[0]
        assert copied.nodes[0]["edge"] is _edge_attrs(copied)
        assert _edge_attrs(copied)["graph"] is copied.graph
        assert copied.payload[0] is copied.nodes[0]
        assert copied.payload[1] is _edge_attrs(copied)
        assert copied.payload[2] is copied.graph


class _CopyNode:
    def __init__(self, name):
        self.name = name
        self.payload = []


@pytest.mark.parametrize("fcls,ncls", _TYPES)
def test_deepcopy_remaps_node_objects_and_attribute_keys(fcls, ncls):
    for cls in (ncls, fcls):
        node = _CopyNode("source")
        graph = cls()
        graph.add_edge(node, "target")
        graph.nodes[node][node] = node
        graph.graph["node"] = node
        copied = copy.deepcopy(graph)
        copied_node = next(n for n in copied if isinstance(n, _CopyNode))
        assert copied_node is not node
        assert copied_node.payload is not node.payload
        assert copied.graph["node"] is copied_node
        assert copied.nodes[copied_node][copied_node] is copied_node
        assert list(copied.neighbors(copied_node)) == ["target"]


@pytest.mark.parametrize("fcls,ncls", _TYPES)
def test_deepcopy_graph_can_be_its_own_node(fcls, ncls):
    for cls in (ncls, fcls):
        graph = cls()
        # Use the supported assigned-store protocol to isolate deepcopy from
        # the native insertion path's handling of a graph used as its own key.
        graph._node = {graph: {"owner": graph}, "target": {}}
        edge = {0: {}} if graph.is_multigraph() else {}
        graph._adj = {graph: {"target": edge}, "target": {}}
        if graph.is_directed():
            graph._pred = {graph: {}, "target": {graph: edge}}
        else:
            graph._adj["target"][graph] = edge
        copied = copy.deepcopy(graph)
        assert copied in copied
        assert graph not in copied
        assert copied.nodes[copied]["owner"] is copied
        assert copied.has_edge(copied, "target")


@pytest.mark.parametrize("fcls,ncls", _TYPES[2:])
def test_deepcopy_remaps_parallel_keys_once(fcls, ncls):
    for cls in (ncls, fcls):
        graph = cls()
        key = _CopyNode("parallel")
        graph.add_edge(0, 1, key=key, identity=key)
        graph.add_edge(0, 1, key="other")
        graph.graph["key"] = key
        copied = copy.deepcopy(graph)
        copied_key = next(iter(copied[0][1]))
        assert copied_key is not key
        assert copied.graph["key"] is copied_key
        assert copied[0][1][copied_key]["identity"] is copied_key
        assert list(copied[0][1])[1:] == ["other"]


@pytest.mark.parametrize("fcls,ncls", _TYPES)
@pytest.mark.parametrize("layer", ["graph", "node", "edge"])
@pytest.mark.parametrize("graph_first", [False, True])
def test_deepcopy_aliases_survive_an_enclosing_container(fcls, ncls, layer, graph_first):
    for cls in (ncls, fcls):
        graph = cls([(0, 1)])
        attrs = _attribute_layer(graph, layer)
        attrs["value"] = 42
        values = [graph, attrs] if graph_first else [attrs, graph]
        copied = copy.deepcopy(values)
        copied_graph, copied_attrs = copied if graph_first else reversed(copied)
        assert _attribute_layer(copied_graph, layer) is copied_attrs
        assert copied_attrs is not attrs


@pytest.mark.parametrize("fcls,ncls", _TYPES)
@pytest.mark.parametrize("layer", ["graph", "node", "edge"])
def test_deepcopy_registers_native_scalar_dicts_in_shared_memo(fcls, ncls, layer):
    for cls in (ncls, fcls):
        graph = cls([(0, 1)])
        attrs = _attribute_layer(graph, layer)
        attrs["value"] = 42
        memo = {}
        copied = copy.deepcopy(graph, memo)
        assert copy.deepcopy(attrs, memo) is _attribute_layer(copied, layer)
        if cls is fcls:
            assert "_fnx_private_node_override" not in vars(copied)


@pytest.mark.parametrize("fcls,ncls", _TYPES)
@pytest.mark.parametrize("layer", ["graph", "node", "edge"])
def test_deepcopy_honors_preseeded_attribute_memo(fcls, ncls, layer):
    for cls in (ncls, fcls):
        graph = cls([(0, 1)])
        attrs = _attribute_layer(graph, layer)
        replacement = {"already_copied": []}
        copied = copy.deepcopy(graph, {id(attrs): replacement})
        assert _attribute_layer(copied, layer) is replacement


@pytest.mark.parametrize("fcls,ncls", _TYPES)
def test_deepcopy_honors_preseeded_atomic_node_memo(fcls, ncls):
    for cls in (ncls, fcls):
        graph = cls([(10, 20)])
        graph.nodes[10]["identity"] = 10
        copied = copy.deepcopy(graph, {id(10): "renamed"})
        assert list(copied) == ["renamed", 20]
        assert copied.has_edge("renamed", 20)
        assert copied.nodes["renamed"]["identity"] == "renamed"


@pytest.mark.parametrize("fcls,ncls", _TYPES)
@pytest.mark.parametrize("layer", ["graph", "node", "edge"])
def test_deepcopy_copies_attribute_keys_with_scalar_values(fcls, ncls, layer):
    for cls in (ncls, fcls):
        graph = cls([(0, 1)])
        key = _CopyNode("attribute key")
        _attribute_layer(graph, layer)[key] = 42
        copied = copy.deepcopy(graph)
        copied_key = next(iter(_attribute_layer(copied, layer)))
        assert copied_key is not key
        assert copied_key.name == key.name
        assert copied_key.payload is not key.payload


@pytest.mark.parametrize("fcls,ncls", _TYPES)
def test_deepcopy_preserves_adjacency_dictionary_aliases(fcls, ncls):
    for cls in (ncls, fcls):
        graph = cls([(0, 1)])
        graph.graph["row"] = graph._adj[0]
        graph.graph["edge"] = graph._adj[0][1]
        copied = copy.deepcopy(graph)
        assert copied.graph["row"] is copied._adj[0]
        assert copied.graph["edge"] is copied._adj[0][1]
        if graph.is_directed():
            assert copied._adj is copied._succ
            assert copied._adj[0][1] is copied._pred[1][0]
        else:
            assert copied._adj[0][1] is copied._adj[1][0]


@pytest.mark.parametrize("fcls,ncls", [_TYPES[1], _TYPES[3]])
def test_deepcopy_honors_preseeded_directed_adjacency_memo(fcls, ncls):
    for cls in (ncls, fcls):
        graph = cls([(0, 1)])
        adjacency = graph._adj
        replacement = {0: {}, 1: {}}
        copied = copy.deepcopy(graph, {id(adjacency): replacement})
        assert copied._adj is replacement
        assert copied._succ is replacement


class _Uncopyable:
    def __deepcopy__(self, memo):
        raise ValueError("cannot copy payload")


@pytest.mark.parametrize("fcls,ncls", _TYPES)
@pytest.mark.parametrize("layer", ["graph", "node", "edge", "instance"])
def test_deepcopy_propagates_user_copy_errors(fcls, ncls, layer):
    for cls in (ncls, fcls):
        graph = cls([(0, 1)])
        _attribute_layer(graph, layer)["payload"] = _Uncopyable()
        with pytest.raises(ValueError, match="^cannot copy payload$"):
            copy.deepcopy(graph)


@pytest.mark.parametrize("fcls,ncls", _TYPES)
def test_deepcopy_subclass_state_and_slots_without_reinitializing(fcls, ncls):
    for cls in (ncls, fcls):
        class CustomGraph(cls):
            __slots__ = ("slot_payload", "__private_payload")

            def __init__(self, payload):
                super().__init__()
                self.payload = payload
                self.slot_payload = payload
                self.__private_payload = payload

            def private_payload(self):
                return self.__private_payload

        payload = []
        graph = CustomGraph(payload)
        graph.add_edge(0, 1)
        graph.graph["payload"] = payload
        copied = copy.deepcopy(graph)
        assert type(copied) is CustomGraph
        assert copied.payload is not payload
        assert copied.payload is copied.slot_payload
        assert copied.payload is copied.private_payload()
        assert copied.payload is copied.graph["payload"]


@pytest.mark.parametrize("fcls,ncls", _TYPES)
def test_deepcopy_private_slot_on_underscore_only_class_name(fcls, ncls):
    for cls in (ncls, fcls):
        custom = type("_", (cls,), {"__slots__": ("__payload",)})
        graph = custom()
        graph.__payload = []
        copied = copy.deepcopy(graph)
        assert copied.__payload == []
        assert copied.__payload is not graph.__payload


@pytest.mark.parametrize("fcls,ncls", _TYPES)
@pytest.mark.parametrize("layer", ["graph", "node", "edge", "instance"])
@pytest.mark.parametrize("name", ["nodes", "edges", "degree", "adj"])
def test_deepcopy_retains_canonical_live_views(fcls, ncls, layer, name):
    for cls in (ncls, fcls):
        graph = cls([(0, 1)])
        view = getattr(graph, name)
        _attribute_layer(graph, layer)["view"] = view
        before = list(view)
        copied = copy.deepcopy(graph)
        copied_view = _attribute_layer(copied, layer)["view"]
        assert copied_view is getattr(copied, name)
        assert list(copied_view) == before
        copied.add_edge(1, 2)
        assert list(copied_view) == list(getattr(copied, name))
        assert list(copied_view) != before
        assert list(view) == before


class _CopyStorageDict(dict):
    def __deepcopy__(self, memo):
        copied = type(self)()
        memo[id(self)] = copied
        copied.copied_by_hook = True
        for key, value in self.items():
            copied[copy.deepcopy(key, memo)] = copy.deepcopy(value, memo)
        return copied


@pytest.mark.parametrize("fcls,ncls", _TYPES)
@pytest.mark.parametrize("layer", ["graph", "node", "edge"])
@pytest.mark.parametrize("name", ["degree", "adj"])
def test_deepcopy_custom_storage_protocol_keeps_live_views(fcls, ncls, layer, name):
    for cls in (ncls, fcls):
        graph = cls()
        attrs = {}
        edge = {0: attrs} if graph.is_multigraph() else attrs
        graph._node = _CopyStorageDict({0: {}, 1: {}})
        graph._adj = _CopyStorageDict({0: {1: edge}, 1: {}})
        if graph.is_directed():
            graph._pred = _CopyStorageDict({0: {}, 1: {0: edge}})
        else:
            graph._adj[1][0] = edge
        view = getattr(graph, name)
        _attribute_layer(graph, layer)["view"] = view
        copied = copy.deepcopy(graph)
        assert isinstance(copied._node, _CopyStorageDict)
        assert isinstance(copied._adj, _CopyStorageDict)
        assert copied._node.copied_by_hook and copied._adj.copied_by_hook
        copied_view = _attribute_layer(copied, layer)["view"]
        assert copied_view is getattr(copied, name)
        assert list(copied_view) == list(view)
        copied.add_node(2)
        assert list(copied_view) == list(getattr(copied, name))
        if name == "degree":
            assert dict(copied_view)[2] == 0
        else:
            assert not copied_view[2]


@pytest.mark.parametrize("fcls,ncls", [_TYPES[1], _TYPES[3]])
@pytest.mark.parametrize("name", ["in_degree", "out_degree", "succ", "pred", "in_edges", "out_edges"])
def test_deepcopy_directional_views_remain_live(fcls, ncls, name):
    for cls in (ncls, fcls):
        graph = cls([(0, 1)])
        graph.graph["view"] = getattr(graph, name)
        copied = copy.deepcopy(graph)
        assert copied.graph["view"] is getattr(copied, name)
        copied.add_edge(1, 2)
        assert list(copied.graph["view"]) == list(getattr(copied, name))
        assert len(copied.graph["view"]) == (2 if name.endswith("edges") else 3)


@pytest.mark.parametrize("fcls,ncls", _TYPES)
@pytest.mark.parametrize("complex_attrs", [False, True])
def test_deepcopy_preserves_order_and_mutable_graph_behavior(fcls, ncls, complex_attrs):
    snapshots = []
    for cls in (ncls, fcls):
        graph = cls()
        graph.add_nodes_from([3, 0, 2, 1])
        graph.add_edges_from([(0, 1), (2, 1), (3, 2), (0, 3), (3, 1)])
        if complex_attrs:
            graph.graph["payload"] = []
        copied = copy.deepcopy(graph)
        snapshots.append((list(copied), [(n, list(copied[n])) for n in copied]))
        copied.remove_node(2)
        copied.add_edge(0, 4)
        assert 2 in graph and 4 not in graph
        assert copied.has_edge(0, 4)
        assert 2 not in copied
    assert snapshots[0] == snapshots[1]


@pytest.mark.parametrize("fcls,ncls", _TYPES)
def test_deepcopy_complex_graph_still_runs_weighted_algorithms(fcls, ncls):
    for library, cls in ((nx, ncls), (fnx, fcls)):
        graph = cls()
        graph.add_weighted_edges_from([(0, 1, 4), (1, 2, 2), (0, 2, 9)])
        graph.graph["owner"] = graph
        copied = copy.deepcopy(graph)
        assert library.shortest_path_length(copied, 0, 2, weight="weight") == 6
        _edge_attrs(copied)["weight"] = 1
        assert library.shortest_path_length(copied, 0, 2, weight="weight") == 3
        assert library.shortest_path_length(graph, 0, 2, weight="weight") == 6
