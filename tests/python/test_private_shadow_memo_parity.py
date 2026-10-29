"""Parity lock for br-r37-c1-8itxk — the method-shadow eligibility memo.

Assigning a networkx private store (``G._node``, ``G._adj``, ...) makes fnx
shadow its raw PyO3 methods on that ONE instance with mapping-aware fallbacks
(br-r37-c1-qmi5w / 6q4wl / 57ba1 / heyxu). The installer used to re-derive,
for every assignment and every method name, whether the class's binding was a
raw method it may shadow — an MRO walk in a Python generator plus an ``any()``.
A reverse view assigns three private stores at construction, so
``DiGraph.reverse(copy=False)`` paid twelve of those walks per call.

That question is a property of the CLASS, so it is now memoised on
(class, method-name). This file pins the two things that makes risky:

* a SUBCLASS must get its own answer rather than inheriting the parent's
  cached one — the memo is keyed on the class for exactly this reason;
* the shadow behaviour itself must be unchanged, so the mapping-aware
  fallbacks still fire when a private store is assigned, on every class.

The behaviour assertions are differential against live networkx.
"""

from __future__ import annotations

import copy

import networkx as nx
import pytest

import franken_networkx as fnx

CLASSES = ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"]


def _build(lib, cls_name):
    graph = getattr(lib, cls_name)()
    graph.add_edge("a", "b", weight=1.0)
    graph.add_edge("b", "c", weight=2.0)
    return graph


@pytest.mark.parametrize("cls_name", CLASSES)
def test_assigned_private_node_store_still_shadows(cls_name):
    """The mechanism the memo sits inside must still work."""
    results = []
    for lib in (nx, fnx):
        graph = _build(lib, cls_name)
        graph._node = {"a": {}, "b": {}, "zz": {}}
        results.append(
            (
                graph.has_node("zz"),
                graph.has_node("c"),
                graph.number_of_nodes(),
                graph.order(),
            )
        )
    assert results[1] == results[0]


@pytest.mark.parametrize("cls_name", CLASSES)
def test_assigned_private_adj_store_still_shadows(cls_name):
    results = []
    for lib in (nx, fnx):
        graph = _build(lib, cls_name)
        inner = {"b": {0: {}}} if graph.is_multigraph() else {"b": {}}
        graph._adj = {"a": inner, "b": {}, "zz": {}}
        results.append((graph.has_edge("a", "b"), graph.has_edge("a", "zz")))
    assert results[1] == results[0]


@pytest.mark.parametrize("cls_name", CLASSES)
def test_a_subclass_gets_its_own_memo_entry(cls_name):
    """The memo is keyed on the CLASS; a subclass override must win.

    If the eligibility answer were cached per method NAME alone, a subclass
    that defines its own has_node would inherit the base class's "shadowable"
    answer and get its override replaced.
    """
    base = getattr(fnx, cls_name)
    sentinel = object()

    class Sub(base):
        def has_node(self, n):  # noqa: D401 - deliberate override
            return sentinel

    graph = Sub()
    graph.add_edge("a", "b")
    assert graph.has_node("a") is sentinel
    # Assigning a private store must NOT replace a genuine subclass override.
    graph._node = {"a": {}, "b": {}}
    assert graph.has_node("a") is sentinel

    # And the base class is unaffected by the subclass's entry.
    plain = base()
    plain.add_edge("a", "b")
    assert plain.has_node("a") is True
    assert plain.has_node("zz") is False


@pytest.mark.parametrize("cls_name", ["DiGraph", "MultiDiGraph"])
def test_reverse_view_is_correct_and_repeatable(cls_name):
    """The row that motivated this: reverse builds via private overrides."""
    for _ in range(3):
        gnx, gfx = _build(nx, cls_name), _build(fnx, cls_name)
        rnx, rfx = gnx.reverse(copy=False), gfx.reverse(copy=False)
        assert sorted(map(str, rfx.edges)) == sorted(map(str, rnx.edges))
        assert sorted(map(str, rfx.nodes)) == sorted(map(str, rnx.nodes))
        assert dict(rfx.in_degree) == dict(rnx.in_degree)
        assert dict(rfx.out_degree) == dict(rnx.out_degree)
        assert rfx["b"]["a"] == rnx["b"]["a"]


@pytest.mark.parametrize("cls_name", ["DiGraph", "MultiDiGraph"])
def test_many_reverse_views_do_not_interfere(cls_name):
    """The memo is shared across instances; instances must not be."""
    gnx, gfx = _build(nx, cls_name), _build(fnx, cls_name)
    views_nx = [gnx.reverse(copy=False) for _ in range(5)]
    views_fx = [gfx.reverse(copy=False) for _ in range(5)]
    for vnx, vfx in zip(views_nx, views_fx):
        assert sorted(map(str, vfx.edges)) == sorted(map(str, vnx.edges))
    # The originals are untouched.
    assert sorted(map(str, gfx.edges)) == sorted(map(str, gnx.edges))


class _PrivateReaders:
    """User read methods must not disable inherited mutation methods."""

    def has_node(self, node):
        return node in self._node

    def number_of_nodes(self):
        return len(self._node)

    order = number_of_nodes

    def has_edge(self, u, v, key=None):
        row = self._adj.get(u, {})
        return v in row and (
            not self.is_multigraph() or key is None or key in row[v]
        )

    def get_edge_data(self, *args, **kwargs):
        # A delegating override keeps both simple/multi signatures and avoids
        # making a separate _adj facade recursion part of this mutation probe.
        return self._private_reader_base.get_edge_data(self, *args, **kwargs)

    def neighbors(self, node):
        return iter(self._adj[node])

    successors = neighbors

    def predecessors(self, node):
        return iter(self._pred[node])


def _private_subclass_pair(cls_name, store, reader_overrides):
    graphs = []
    seed = getattr(nx, cls_name)()
    seed.add_edges_from([(0, 1, {"weight": 2}), (1, 2, {"weight": 3}), (2, 2, {"weight": 5})])
    seed.add_node(9, marker="isolated")
    for lib in (nx, fnx):
        base = getattr(lib, cls_name)
        if reader_overrides is None:
            graph_class = base
        else:
            bases = (_PrivateReaders, base) if reader_overrides else (base,)
            graph_class = type("PrivateGraph", bases, {"_private_reader_base": base})
        graph = graph_class(seed)
        graph.graph["name"] = "private storage"
        setattr(graph, store, copy.deepcopy(getattr(seed, store)))
        graphs.append(graph)
    return graphs


def _private_storage_snapshot(graph):
    def adjacency(mapping):
        return [
            (
                node,
                [
                    (
                        neighbor,
                        [(key, dict(attrs)) for key, attrs in data.items()]
                        if graph.is_multigraph() else dict(data),
                    )
                    for neighbor, data in row.items()
                ],
            )
            for node, row in mapping.items()
        ]

    return (
        [(node, dict(attrs)) for node, attrs in graph._node.items()],
        adjacency(graph._adj),
        adjacency(graph._pred) if graph.is_directed() else None,
        dict(graph.graph),
    )


def _mutate_private_graph(graph, operation):
    if operation == "add_node":
        return graph.add_node(5, color="blue")
    if operation == "add_nodes_from":
        return graph.add_nodes_from([(5, {"color": "blue"}), 6], common=True)
    if operation == "add_edge":
        return graph.add_edge(2, 5, weight=11)
    if operation == "add_edges_from":
        return graph.add_edges_from([(2, 5, {"weight": 11}), (5, 6)])
    if operation == "add_weighted_edges_from":
        return graph.add_weighted_edges_from([(2, 5, 11), (5, 6, 7)], kind="new")
    if operation == "remove_node":
        return graph.remove_node(1)
    if operation == "remove_edge":
        return graph.remove_edge(0, 1)
    if operation == "remove_edges_from":
        return graph.remove_edges_from([(0, 1), (77, 78)])
    if operation == "clear_edges":
        return graph.clear_edges()
    if operation == "clear":
        return graph.clear()
    raise AssertionError(operation)


@pytest.mark.parametrize("cls_name", CLASSES)
@pytest.mark.parametrize("store", ["_node", "_adj"])
@pytest.mark.parametrize(
    "reader_overrides", [None, False, True],
    ids=["concrete-control", "plain-subclass", "custom-readers"],
)
@pytest.mark.parametrize("operation", [
    "add_node", "add_nodes_from", "add_edge", "add_edges_from", "add_weighted_edges_from",
    "remove_node", "remove_edge", "remove_edges_from", "clear_edges", "clear",
])
def test_subclass_mutations_update_both_halves_of_private_storage(
    cls_name, store, reader_overrides, operation
):
    expected, actual = _private_subclass_pair(cls_name, store, reader_overrides)
    expected_store, actual_store = getattr(expected, store), getattr(actual, store)
    assert _mutate_private_graph(actual, operation) == _mutate_private_graph(expected, operation)
    assert getattr(actual, store) is actual_store
    assert getattr(expected, store) is expected_store
    assert _private_storage_snapshot(actual) == _private_storage_snapshot(expected)


@pytest.mark.parametrize("cls_name", ["MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("subclass", [False, True], ids=["concrete-control", "subclass"])
@pytest.mark.parametrize("self_loop", [False, True], ids=["pair", "self-loop"])
@pytest.mark.parametrize("operation", ["last", "key", "missing-key", "batch"])
def test_multigraph_private_removal_preserves_remaining_keys(
    cls_name, subclass, self_loop, operation
):
    u, v = (0, 0) if self_loop else (0, 1)
    seed = getattr(nx, cls_name)()
    for key in ("first", "middle", "last"):
        seed.add_edge(u, v, key=key, label=key)
    graphs = []
    for lib in (nx, fnx):
        base = getattr(lib, cls_name)
        graph_class = type("PrivateKeys", (base,), {}) if subclass else base
        graph = graph_class(seed)
        nodes, rows, pred = copy.deepcopy((
            seed._node, seed._adj, seed._pred if seed.is_directed() else None,
        ))
        graph._node, graph._adj = nodes, rows
        if graph.is_directed():
            graph._pred = pred
        if operation == "last":
            graph.remove_edge(u, v)
        elif operation == "key":
            graph.remove_edge(u, v, "first")
        elif operation == "missing-key":
            with pytest.raises(nx.NetworkXError, match="with key missing"):
                graph.remove_edge(u, v, "missing")
        else:
            graph.remove_edges_from([
                (u, v, "missing"), (u, v, "first", {"ignored": True}), (u, v),
            ])
        reverse = graph._pred if graph.is_directed() else graph._adj
        assert graph._adj[u][v] is reverse[v][u]
        graphs.append(graph)
    expected, actual = graphs
    assert _private_storage_snapshot(actual) == _private_storage_snapshot(expected)


@pytest.mark.parametrize("cls_name", CLASSES)
@pytest.mark.parametrize("subclass", [False, True], ids=["concrete-control", "subclass"])
def test_native_components_follow_reassigned_subclass_storage(cls_name, subclass):
    graphs = []
    desired = getattr(nx, cls_name)()
    desired.add_nodes_from(range(4))
    desired.add_edges_from([(0, 1), (2, 3)])
    for lib in (nx, fnx):
        base = getattr(lib, cls_name)
        graph_class = type("PrivateComponents", (base,), {}) if subclass else base
        graph = graph_class([(0, 1), (1, 2), (2, 3), (3, 0)])
        nodes, rows, pred = copy.deepcopy((
            desired._node, desired._adj, desired._pred if desired.is_directed() else None,
        ))
        graph._node, graph._adj = nodes, rows
        if graph.is_directed():
            graph._pred = pred
        graphs.append(graph)

    def components(lib, graph):
        if graph.is_directed():
            return (
                lib.number_weakly_connected_components(graph),
                {frozenset(part) for part in lib.weakly_connected_components(graph)},
                {frozenset(part) for part in lib.strongly_connected_components(graph)},
                lib.is_directed_acyclic_graph(graph),
            )
        return (
            lib.number_connected_components(graph),
            {frozenset(part) for part in lib.connected_components(graph)},
            lib.is_connected(graph),
        )

    expected, actual = graphs
    before = components(nx, expected)
    assert before[0] == 2, "private rows must differ from the connected native cycle"
    assert components(fnx, actual) == before
    for graph in graphs:
        data = {0: {}} if graph.is_multigraph() else {}
        graph._adj[1][2] = data
        if graph.is_directed():
            graph._pred[2][1] = data
        else:
            graph._adj[2][1] = data
    after = components(nx, expected)
    assert after[0] == 1
    assert components(fnx, actual) == after
