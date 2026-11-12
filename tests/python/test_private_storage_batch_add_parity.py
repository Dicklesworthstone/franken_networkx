"""br-r37-c1-wv3cu: the batch add methods write INTO the assigned mapping.

networkx defines add_edges_from and add_weighted_edges_from in terms of add_edge,
so fixing add_edge fixed them there for free. fnx's are native kernels that never
reach the corrected path — the same asymmetry add_nodes_from showed. Each batch
method therefore needs its own shadow, and "the singular is fixed so the plural
is too" is exactly the assumption that would have left these broken.

The fixture shares the inner row object between both directions of an undirected
edge, because that is networkx's own invariant (``_adj[u][v] is _adj[v][u]``).
Building them separately produces a mapping no real networkx graph holds and
manufactures a divergence that is the fixture's, not the code's.
"""

import copy
from collections import UserDict

import networkx as nx
import pytest

import franken_networkx as fnx

ALL = ["Graph", "MultiGraph", "DiGraph", "MultiDiGraph"]


def pair(cls):
    out = []
    multi = cls.startswith("Multi")
    for mod in (nx, fnx):
        g = getattr(mod, cls)()
        g.add_edge("a", "b")
        shared = {0: {}} if multi else {}
        m = {"a": {"b": shared}, "b": {"a": shared}}
        g._adj = m
        out.append((g, m))
    return out


def state(g):
    return (
        sorted(map(str, g.nodes)),
        sorted(str(tuple(map(str, e[:2]))) for e in g.edges),
        sorted(map(str, g.adj)),
    )


@pytest.mark.parametrize("cls", ALL)
def test_add_edges_from_reaches_the_callers_object(cls):
    (gnx, mnx), (gfx, mfx) = pair(cls)
    for g in (gnx, gfx):
        g.add_edges_from([("p", "q"), ("q", "r")])
    assert sorted(map(str, mfx)) == sorted(map(str, mnx))
    assert state(gfx) == state(gnx)


@pytest.mark.parametrize("cls", ALL)
def test_add_edges_from_with_data_dicts(cls):
    (gnx, _), (gfx, _) = pair(cls)
    for g in (gnx, gfx):
        g.add_edges_from([("p", "q", {"w": 1})], tag="t")
    assert state(gfx) == state(gnx)
    assert gfx.get_edge_data("p", "q") == gnx.get_edge_data("p", "q")


@pytest.mark.parametrize("cls", ALL)
def test_add_weighted_edges_from(cls):
    (gnx, mnx), (gfx, mfx) = pair(cls)
    for g in (gnx, gfx):
        g.add_weighted_edges_from([("x", "y", 3), ("y", "z", 4.5)])
    assert sorted(map(str, mfx)) == sorted(map(str, mnx))
    assert state(gfx) == state(gnx)
    assert gfx.get_edge_data("x", "y") == gnx.get_edge_data("x", "y")


@pytest.mark.parametrize("cls", ALL)
def test_a_custom_weight_key_is_honoured(cls):
    (gnx, _), (gfx, _) = pair(cls)
    for g in (gnx, gfx):
        g.add_weighted_edges_from([("x", "y", 2)], weight="cost")
    assert gfx.get_edge_data("x", "y") == gnx.get_edge_data("x", "y")


@pytest.mark.parametrize("cls", ["MultiGraph", "MultiDiGraph"])
def test_multigraph_key_arity_forms(cls):
    """The 3-tuple is ambiguous on a multigraph: a KEY if it is not a mapping."""
    (gnx, _), (gfx, _) = pair(cls)
    for g in (gnx, gfx):
        g.add_edges_from([("p", "q", "mykey"), ("r", "s", {"w": 1})])
    assert state(gfx) == state(gnx)
    assert sorted(map(str, gfx.edges(keys=True))) == sorted(map(str, gnx.edges(keys=True)))


@pytest.mark.parametrize("cls", ALL)
def test_ordinary_graphs_are_unchanged(cls):
    """Negative control: no assignment, so no shadow is installed."""
    gnx = getattr(nx, cls)()
    gfx = getattr(fnx, cls)()
    for g in (gnx, gfx):
        g.add_edges_from([("a", "b", {"w": 1}), ("b", "c")])
        g.add_weighted_edges_from([("c", "d", 7)])
    assert state(gfx) == state(gnx)
    assert gfx.get_edge_data("c", "d") == gnx.get_edge_data("c", "d")
    assert not {"add_edges_from", "add_weighted_edges_from"} & set(vars(gfx))


STORAGE_CASES = [
    (cls, storage)
    for cls in ALL
    for storage in ("native", "_node", "_adj", "all", "_pred")
    if storage != "_pred" or cls in ("DiGraph", "MultiDiGraph")
]


def _attribute_graph_pair(cls, storage):
    seed = getattr(nx, cls)()
    seed.add_nodes_from([0, 1, 2])
    seed.nodes[0]["retained"] = "node"
    seed.add_edge(0, 1, retained="edge")
    graphs = []
    for mod in (nx, fnx):
        graph = getattr(mod, cls)()
        graph.add_nodes_from([0, 1, 2])
        graph.nodes[0]["retained"] = "node"
        graph.add_edge(0, 1, retained="edge")
        nodes, adjacency, predecessors = copy.deepcopy((
            seed._node, seed._adj, seed._pred if seed.is_directed() else None,
        ))
        if storage in ("_node", "all"):
            graph._node = nodes
        if storage in ("_adj", "all"):
            graph._adj = adjacency
        if graph.is_directed() and storage in ("_pred", "all"):
            graph._pred = predecessors
        graphs.append(graph)
    return graphs


def _attribute_storage_state(graph):
    def rows(mapping):
        result = []
        for node, neighbors in mapping.items():
            entries = []
            for neighbor, data in neighbors.items():
                if graph.is_multigraph():
                    data = [(key, list(attrs.items())) for key, attrs in data.items()]
                else:
                    data = list(data.items())
                entries.append((neighbor, data))
            result.append((node, entries))
        return result

    return (
        [(node, list(attrs.items())) for node, attrs in graph._node.items()],
        rows(graph._adj),
        rows(graph._pred) if graph.is_directed() else None,
    )


@pytest.mark.parametrize("cls,storage", STORAGE_CASES)
@pytest.mark.parametrize("existing", [False, True], ids=["new-edge", "existing-edge"])
@pytest.mark.parametrize(
    "data",
    [
        {"before": "local", "weight": 2.5, "after": "last"},
        {
            "before": "local", "self": "metadata", "key": "attribute", "u_of_edge": "u",
            "v_of_edge": "v", "u_for_edge": "source", "v_for_edge": "target",
            "after": "last",
        },
        {"before": "local", 17: "integer", ("metadata", 2): [4, 5], "after": "last"},
    ],
    ids=["ordinary", "parameter-names", "non-string-keys"],
)
def test_private_edge_batch_keeps_attribute_mapping(cls, storage, existing, data):
    outcomes = []
    for graph in _attribute_graph_pair(cls, storage):
        u, v = (0, 1) if existing else (1, 2)
        if graph.is_multigraph():
            edge = (u, v, 0 if existing else "fresh", data)
        else:
            edge = (u, v, data)
        result = graph.add_edges_from([edge], broadcast="common", before="broadcast")
        outcomes.append((result, _attribute_storage_state(graph)))
    assert outcomes[1] == outcomes[0]


@pytest.mark.parametrize("cls,storage", STORAGE_CASES)
@pytest.mark.parametrize("data_type", [UserDict, tuple], ids=["mapping", "pairs"])
def test_private_edge_batch_accepts_mapping_and_pair_data(cls, storage, data_type):
    outcomes = []
    data = data_type([("color", "blue"), (17, "integer")])
    for graph in _attribute_graph_pair(cls, storage):
        result = graph.add_edges_from([(1, 2, data)], broadcast="common")
        outcomes.append((result, _attribute_storage_state(graph)))
    assert outcomes[1] == outcomes[0]


@pytest.mark.parametrize("cls,storage", STORAGE_CASES)
@pytest.mark.parametrize("weight", ["key", 17], ids=["parameter-name", "non-string"])
def test_private_weighted_batch_keeps_custom_weight_key(cls, storage, weight):
    outcomes = []
    for graph in _attribute_graph_pair(cls, storage):
        result = graph.add_weighted_edges_from(
            [(1, 2, 3.25)], weight=weight, before="first", after="last"
        )
        outcomes.append((result, _attribute_storage_state(graph)))
    assert outcomes[1] == outcomes[0]


@pytest.mark.parametrize("method", ["single", "batch", "weighted"])
def test_pred_only_new_parallel_pair_keeps_live_keydict(method):
    outcomes = []
    for graph in _attribute_graph_pair("MultiDiGraph", "_pred"):
        if method == "single":
            graph.add_edge(1, 2, weight=3.25)
        elif method == "batch":
            graph.add_edges_from([(1, 2, {"weight": 3.25})])
        else:
            graph.add_weighted_edges_from([(1, 2, 3.25)])
        held = graph.get_edge_data(1, 2)
        assert graph._pred[2][1] is held
        graph.add_edges_from([(1, 2, {"weight": 5})])
        assert graph._pred[2][1] is held
        held["manual"] = {"tag": "held"}
        assert graph.get_edge_data(1, 2, "manual") is held["manual"]
        before_removal = _attribute_storage_state(graph)
        graph.remove_edges_from([(1, 2, key) for key in list(held)])
        outcomes.append((before_removal, _attribute_storage_state(graph)))
    assert outcomes[1] == outcomes[0]


@pytest.mark.parametrize("method", ["single", "batch", "weighted"])
def test_adj_only_new_parallel_pair_keeps_live_keydict(method):
    outcomes = []
    for graph in _attribute_graph_pair("MultiDiGraph", "_adj"):
        if method == "single":
            graph.add_edge(1, 2, weight=3.25)
        elif method == "batch":
            graph.add_edges_from([(1, 2, {"weight": 3.25})])
        else:
            graph.add_weighted_edges_from([(1, 2, 3.25)])
        held = graph.get_edge_data(1, 2)
        graph.add_edges_from([(1, 2, {"weight": 5})])
        assert list(graph._pred[2][1]) == list(held)
        assert graph._pred[2][1] is held
        held["manual"] = {"tag": "held"}
        assert graph.get_edge_data(1, 2, "manual") is held["manual"]
        before_removal = _attribute_storage_state(graph)
        graph.remove_edges_from([(1, 2, key) for key in list(held)])
        outcomes.append((before_removal, _attribute_storage_state(graph)))
    assert outcomes[1] == outcomes[0]


@pytest.mark.parametrize("native_keys", [(0.0,), ("stale", "old"), ()])
def test_new_private_pair_replaces_stale_native_rows_without_mutating_held_data(native_keys):
    outcomes = []
    for mod in (nx, fnx):
        graph = mod.MultiDiGraph()
        for key in native_keys or ("placeholder",):
            graph.add_edge(0, 1, key=key, retained=repr(key))
        held_old = graph.get_edge_data(0, 1)
        if not native_keys:
            held_old.clear()
        graph.add_edge(2, 1, key="later", neighbor="keep")
        held_predecessors = graph._pred[1]
        predecessor_iter = iter(held_predecessors)
        assert next(predecessor_iter) == 0
        graph._adj = {0: {}, 1: {}, 2: {1: {"later": {"neighbor": "keep"}}}}
        keys = graph.add_edges_from([(0, 1, {"fresh": "first"}), (0, 1, {"fresh": "second"})])
        assert next(iter(graph.get_edge_data(0, 1))) is keys[0]
        assert list(held_predecessors) == [0, 2]
        assert list(predecessor_iter) == [2]
        outcomes.append((keys, _attribute_storage_state(graph), list(held_old.items())))
        before_detached_write = _attribute_storage_state(graph)
        held_old["detached"] = {"only": "old"}
        assert _attribute_storage_state(graph) == before_detached_write
    assert outcomes[1] == outcomes[0]


@pytest.mark.parametrize("cls,storage", STORAGE_CASES)
@pytest.mark.parametrize("existing", [False, True], ids=["new-node", "existing-node"])
@pytest.mark.parametrize(
    "data",
    [
        {"before": "local", "color": "blue", "after": "last"},
        {
            "before": "local", "self": "metadata", "node_for_adding": "attribute",
            "_sync_native": False, "_preserve_assigned_row": True,
            "after": "last",
        },
        {"before": "local", 17: "integer", ("metadata", 2): [4, 5], "after": "last"},
    ],
    ids=["ordinary", "parameter-and-control-names", "non-string-keys"],
)
def test_private_node_batch_keeps_attribute_mapping(cls, storage, existing, data):
    outcomes = []
    for graph in _attribute_graph_pair(cls, storage):
        node = 0 if existing else 3
        result = graph.add_nodes_from([(node, data)], broadcast="common", before="broadcast")
        outcomes.append((result, _attribute_storage_state(graph)))
    assert outcomes[1] == outcomes[0]


@pytest.mark.parametrize("cls,storage", STORAGE_CASES)
@pytest.mark.parametrize("data_type", [UserDict, list], ids=["mapping", "pairs"])
def test_private_node_batch_accepts_mapping_and_pair_data(cls, storage, data_type):
    outcomes = []
    data = data_type([("color", "blue"), (17, "integer")])
    for graph in _attribute_graph_pair(cls, storage):
        result = graph.add_nodes_from([(3, data)], broadcast="common")
        outcomes.append((result, _attribute_storage_state(graph)))
    assert outcomes[1] == outcomes[0]


def _removal_graph_pair(storage, self_loop=False):
    graphs = []
    v = 0 if self_loop else 1
    for mod in (nx, fnx):
        graph = mod.MultiDiGraph()
        graph.add_nodes_from([0, 1, 2])
        graph.add_edge(0, v, key="first", origin="native-first")
        graph.add_edge(0, v, key="last", origin="native-last")
        graph.add_edge(2, v, key="other", origin="untouched")
        if storage == "_node":
            graph._node = {node: {} for node in (0, 1, 2)}
        if storage in ("_adj", "both", "shared"):
            forward = {
                "first": {"origin": "forward-first"},
                "last": {"origin": "forward-last"},
            }
            adjacency = {node: {} for node in (0, 1, 2)}
            adjacency[0][v] = forward
            adjacency[2][v] = {"other": {"origin": "untouched"}}
            graph._adj = adjacency
        if storage in ("_pred", "both", "shared"):
            predecessors = {node: {} for node in (0, 1, 2)}
            predecessors[v][0] = (
                forward if storage == "shared" else {
                    "reverse-only": {"origin": "reverse-only"},
                    "last": {"origin": "reverse-last"},
                    "first": {"origin": "reverse-first"},
                }
            )
            predecessors[v][2] = {"other": {"origin": "untouched"}}
            graph._pred = predecessors
        graphs.append(graph)
    return graphs


def _remove_edge_outcome(graph, v, key, method):
    try:
        if method == "single":
            result = graph.remove_edge(0, v, key=key)
        else:
            result = graph.remove_edges_from([(0, v, key)])
    except Exception as exc:  # noqa: BLE001 - compare the mutation/error contract
        return type(exc).__name__, exc.args
    return "ok", result


@pytest.mark.parametrize("storage", ["native", "_node", "_pred", "_adj", "both", "shared"])
@pytest.mark.parametrize("self_loop", [False, True], ids=["edge", "loop"])
@pytest.mark.parametrize("method", ["single", "batch"])
@pytest.mark.parametrize("key", [None, "first", "reverse-only"], ids=["automatic", "explicit", "reverse-only"])
def test_private_parallel_removal_uses_forward_keys(storage, self_loop, method, key):
    outcomes = []
    v = 0 if self_loop else 1
    for graph in _removal_graph_pair(storage, self_loop):
        held_forward = graph.get_edge_data(0, v)
        held_reverse = graph._pred[v][0]
        result = _remove_edge_outcome(graph, v, key, method)
        outcomes.append((
            result, _attribute_storage_state(graph),
            list(held_forward.items()), list(held_reverse.items()),
        ))
    assert outcomes[1] == outcomes[0]


@pytest.mark.parametrize("storage", ["native", "_node", "_pred", "_adj", "both", "shared"])
@pytest.mark.parametrize("self_loop", [False, True], ids=["edge", "loop"])
@pytest.mark.parametrize("method", ["single", "batch"])
def test_private_parallel_last_removal_preserves_detached_reverse_data(storage, self_loop, method):
    outcomes = []
    v = 0 if self_loop else 1
    for graph in _removal_graph_pair(storage, self_loop):
        held_forward = graph.get_edge_data(0, v)
        held_reverse = graph._pred[v][0]
        results = [_remove_edge_outcome(graph, v, key, method) for key in ("first", "last")]
        outcomes.append((
            results, _attribute_storage_state(graph),
            list(held_forward.items()), list(held_reverse.items()),
        ))
        before_detached_write = _attribute_storage_state(graph)
        held_reverse["detached"] = {"origin": "held"}
        assert _attribute_storage_state(graph) == before_detached_write
    assert outcomes[1] == outcomes[0]


@pytest.mark.parametrize("remaining", [1, 2])
@pytest.mark.parametrize("method", ["single", "batch"])
@pytest.mark.parametrize("key", [None, "first"], ids=["automatic", "explicit"])
def test_private_parallel_removal_with_missing_reverse_pair(remaining, method, key):
    outcomes = []
    for mod in (nx, fnx):
        graph = mod.MultiDiGraph()
        graph.add_edge(0, 1, key="first", origin="forward-first")
        if remaining == 2:
            graph.add_edge(0, 1, key="last", origin="forward-last")
        graph._pred = {0: {}, 1: {}}
        held_forward = graph.get_edge_data(0, 1)
        result = _remove_edge_outcome(graph, 1, key, method)
        outcomes.append((result, _attribute_storage_state(graph), list(held_forward.items())))
    assert outcomes[1] == outcomes[0]


@pytest.mark.parametrize("cls", ["MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("self_loop", [False, True], ids=["edge", "loop"])
@pytest.mark.parametrize("arity", [2, 3, 4])
def test_parallel_batch_none_key_removes_the_latest_edge(cls, self_loop, arity):
    outcomes = []
    v = 0 if self_loop else 1
    for mod in (nx, fnx):
        graph = getattr(mod, cls)()
        graph.add_edge(0, v, key="first", origin="keep")
        graph.add_edge(0, v, key="last", origin="remove")
        held = graph.get_edge_data(0, v)
        edge = (0, v, None, {"ignored": "edge data"})[:arity]
        graph.remove_edges_from([(9, 8, None), edge, (0, v, "missing")])
        outcomes.append((_attribute_storage_state(graph), list(held.items())))
    assert outcomes[1] == outcomes[0]


@pytest.mark.parametrize("alias", ["outer", "rows", "keydicts", "rows-and-forward"])
@pytest.mark.parametrize("method", ["single", "batch"])
def test_private_parallel_removal_accepts_live_predecessor_aliases(alias, method):
    outcomes = []
    for graph in _removal_graph_pair("native"):
        predecessors = graph._pred
        if alias == "outer":
            graph._pred = predecessors
        elif alias in ("rows", "rows-and-forward"):
            graph._pred = {node: predecessors[node] for node in predecessors}
        else:
            graph._pred = {
                node: dict(predecessors[node].items()) for node in predecessors
            }
        if alias == "rows-and-forward":
            graph._adj = {
                node: {neighbor: dict(keys) for neighbor, keys in row.items()}
                for node, row in graph._adj.items()
            }
        held_keys = graph.get_edge_data(0, 1)
        held_row = graph._pred[1]
        results = [_remove_edge_outcome(graph, 1, key, method) for key in ("first", "last")]
        outcomes.append((
            results, _attribute_storage_state(graph), list(held_keys.items()), list(held_row),
        ))
    assert outcomes[1] == outcomes[0]
