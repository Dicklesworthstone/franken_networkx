"""``copy.copy(G)`` must share storage with its source, as networkx's does.

br-r37-c1-copyshare-2h5uj / br-r37-c1-epic-storage-architecture-yr2oc.3:
networkx defines no ``__copy__`` on Graph, so ``copy.copy(G)`` takes the default:
a new instance whose ``__dict__`` is copied shallowly, which means ``_adj`` and
``_node`` are the SAME dict objects. Everything is therefore shared -- the graph
attrs dict, every node and edge attr dict, and the STRUCTURE itself: adding a
node or an edge to the source appears in the copy, and vice versa.
"""

import copy as copymod

import networkx as nx
import pytest

import franken_networkx as fnx

CLASSES = ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"]


def _build(module, cls_name):
    graph = getattr(module, cls_name)()
    graph.graph["gattr"] = "orig"
    graph.add_node("a", nattr="orig")
    graph.add_edge("a", "b", eattr="orig")
    return graph


def _edge_attrs(graph, cls_name):
    return graph["a"]["b"][0] if cls_name.startswith("Multi") else graph["a"]["b"]


def _observe(cls_name, mutate, observe):
    """Write through the SOURCE, report what the copy sees, for both libraries."""
    seen = {}
    for name, module in (("nx", nx), ("fnx", fnx)):
        source = _build(module, cls_name)
        duplicate = copymod.copy(source)
        mutate(source, cls_name)
        seen[name] = observe(duplicate, cls_name)
    return seen


@pytest.mark.parametrize("cls_name", CLASSES)
def test_shallow_copy_shares_the_graph_attrs_dict(cls_name):
    seen = _observe(
        cls_name,
        lambda g, c: g.graph.__setitem__("gattr", "changed"),
        lambda g, c: g.graph.get("gattr"),
    )
    assert seen["fnx"] == seen["nx"], (
        f"{cls_name}: copy.copy must share the graph attrs dict. networkx gave "
        f"{seen['nx']!r}, fnx gave {seen['fnx']!r}."
    )


@pytest.mark.parametrize("cls_name", CLASSES)
def test_shallow_copy_shares_node_attr_dicts(cls_name):
    seen = _observe(
        cls_name,
        lambda g, c: g.nodes["a"].__setitem__("nattr", "changed"),
        lambda g, c: g.nodes["a"].get("nattr"),
    )
    assert seen["fnx"] == seen["nx"], (
        f"{cls_name}: networkx gave {seen['nx']!r}, fnx gave {seen['fnx']!r}."
    )


@pytest.mark.parametrize("cls_name", CLASSES)
def test_shallow_copy_shares_edge_attr_dicts(cls_name):
    seen = _observe(
        cls_name,
        lambda g, c: _edge_attrs(g, c).__setitem__("eattr", "changed"),
        lambda g, c: _edge_attrs(g, c).get("eattr"),
    )
    assert seen["fnx"] == seen["nx"], (
        f"{cls_name}: networkx gave {seen['nx']!r}, fnx gave {seen['fnx']!r}."
    )


@pytest.mark.parametrize("cls_name", CLASSES)
@pytest.mark.parametrize("what", ["node", "edge"])
def test_shallow_copy_shares_structure(cls_name, what):
    """nx shares `_adj`/`_node` outright so structural mutations are visible in both."""
    if what == "node":
        seen = _observe(
            cls_name,
            lambda g, c: g.add_node("zz"),
            lambda g, c: "zz" in g,
        )
    else:
        seen = _observe(
            cls_name,
            lambda g, c: g.add_edge("q", "r"),
            lambda g, c: g.has_edge("q", "r"),
        )
    assert seen["fnx"] == seen["nx"], (
        f"{cls_name}: adding a {what} to the source must be visible in copy.copy's result. "
        f"networkx gave {seen['nx']!r}, fnx gave {seen['fnx']!r}."
    )


@pytest.mark.parametrize("cls_name", CLASSES)
def test_shallow_copy_bidirectional_mutations_and_private_dict_identity(cls_name):
    fg = _build(fnx, cls_name)
    ng = _build(nx, cls_name)
    fc = copymod.copy(fg)
    nc = copymod.copy(ng)

    assert fc.graph is fg.graph
    assert fc._node is fg._node
    assert fc._adj is fg._adj
    if fg.is_directed():
        assert fc._succ is fg._succ
        assert fc._pred is fg._pred

    fc.add_node("from_copy", tag=7)
    nc.add_node("from_copy", tag=7)
    fc.add_edge("b", "from_copy", weight=3.5)
    nc.add_edge("b", "from_copy", weight=3.5)

    assert ("from_copy" in fg) == ("from_copy" in ng) is True
    assert fg.nodes["from_copy"] == ng.nodes["from_copy"] == {"tag": 7}
    assert fg.has_edge("b", "from_copy") == ng.has_edge("b", "from_copy") is True
    assert dict(fg.degree()) == dict(ng.degree())


@pytest.mark.parametrize("cls_name", CLASSES)
@pytest.mark.parametrize("frozen", [False, True])
def test_concrete_shallow_copy_preserves_inherited_slot_state(cls_name, frozen):
    def observe(module):
        calls = []

        class BaseGraph(getattr(module, cls_name)):
            __slots__ = "base_payload"

        class CustomGraph(BaseGraph):
            __slots__ = ("payload", "__private_payload", "unset", "source")

            def __init__(self, required):
                calls.append(required)
                super().__init__()

            def set_private(self, value):
                self.__private_payload = value

            def get_private(self):
                return self.__private_payload

        graph = CustomGraph(None)
        graph.add_edge(0, 1)
        shared = []
        graph.base_payload = shared
        graph.payload = shared
        graph.set_private(shared)
        graph.user_payload = shared
        graph.source = graph
        if frozen:
            module.freeze(graph)

        def no_init(self, *args, **kwargs):
            raise AssertionError("shallow copying reran subclass initialization")

        CustomGraph.__init__ = no_init
        duplicate = copymod.copy(graph)
        assert type(duplicate) is CustomGraph
        assert vars(duplicate) is not vars(graph)
        assert duplicate.base_payload is shared
        assert duplicate.payload is shared
        assert duplicate.get_private() is shared
        assert duplicate.user_payload is shared
        assert duplicate.source is graph
        with pytest.raises(AttributeError):
            vars(CustomGraph)["unset"].__get__(duplicate, type(duplicate))
        assert calls == [None]
        assert module.is_frozen(duplicate) is frozen

        shared.append("live")
        assert duplicate.base_payload == ["live"]
        duplicate.payload = ["replacement"]
        duplicate.set_private(["private replacement"])
        assert graph.payload is shared
        assert graph.get_private() is shared
        if not frozen:
            duplicate.add_edge(1, 2)
            assert graph.has_edge(1, 2)
        return list(duplicate), list(duplicate.edges)

    assert observe(fnx) == observe(nx)


VIEW_CASES = [
    (cls_name, kind)
    for cls_name in CLASSES
    for kind in (
        "filtered", "subgraph", "edge_subgraph", "generic", "directed",
        "undirected", "nested", "reverse",
    )
    if kind != "reverse" or cls_name in ("DiGraph", "MultiDiGraph")
]


def _live_view(module, cls_name, kind):
    graph = getattr(module, cls_name)()
    graph.graph["label"] = "original"
    graph.add_nodes_from((node, {"value": node}) for node in range(5))
    if graph.is_multigraph():
        graph.add_edges_from([
            (0, 1, "first", {"weight": 2}),
            (0, 1, "second", {"weight": 3}),
            (1, 2, "first", {"weight": 4}),
            (2, 3, "first", {"weight": 5}),
        ])
    else:
        graph.add_weighted_edges_from([(0, 1, 2), (1, 2, 4), (2, 3, 5)])
    visible = set(range(7))
    blocked = set()
    calls = []

    def node_ok(node):
        calls.append(("node", node))
        return node in visible

    def edge_ok(u, v, *key):
        calls.append(("edge", u, v, *key))
        return (u, v) not in blocked

    if kind == "filtered":
        view = module.subgraph_view(graph, filter_node=node_ok, filter_edge=edge_ok)
    elif kind == "subgraph":
        view = graph.subgraph(range(5))
    elif kind == "edge_subgraph":
        edges = [(0, 1, "first"), (1, 2, "first")] if graph.is_multigraph() else [(0, 1), (1, 2)]
        view = graph.edge_subgraph(edges)
    elif kind == "generic":
        view = graph.copy(as_view=True)
    elif kind == "directed":
        view = graph.to_directed(as_view=True)
    elif kind == "undirected":
        view = graph.to_undirected(as_view=True)
    elif kind == "nested":
        parent = graph.to_directed(as_view=True).reverse(copy=False)
        view = module.subgraph_view(parent, filter_node=node_ok, filter_edge=edge_ok)
    else:
        view = graph.reverse(copy=False)
    return graph, view, visible, blocked, calls


def _view_state(graph):
    options = {"keys": True} if graph.is_multigraph() else {}
    return (
        dict(graph.graph), list(graph.nodes(data=True)),
        list(graph.edges(data=True, **options)),
        [(node, list(graph.adj[node])) for node in graph],
        list(graph.degree()),
    )


@pytest.mark.parametrize("cls_name,kind", VIEW_CASES)
def test_shallow_view_copy_keeps_live_topology_and_attribute_identity(cls_name, kind):
    def observe(module):
        graph, view, visible, blocked, _ = _live_view(module, cls_name, kind)
        # Warm public caches before copying: a shallow copy shares their values.
        _view_state(view)
        duplicate = copymod.copy(view)
        assert duplicate is not view
        assert type(duplicate) is type(view)
        assert vars(duplicate) is not vars(view)
        assert duplicate.graph is view.graph
        assert duplicate.nodes[1] is view.nodes[1]
        assert module.is_frozen(duplicate)
        with pytest.raises(module.NetworkXError):
            duplicate.add_node("forbidden")

        snapshots = []
        for phase in range(4):
            if phase == 0:
                graph.graph["label"] = "changed"
                graph.nodes[1]["value"] = 100
                edge = next(iter(view.edges))
                attrs = view.get_edge_data(*edge)
                assert duplicate.get_edge_data(*edge) is attrs
                attrs["through_view"] = True
            elif phase == 1:
                graph.add_edge(0, 2, weight=8)
                graph.add_edge(2, 6, weight=9)
                if graph.is_multigraph():
                    graph.remove_edge(0, 1, "first")
                else:
                    graph.remove_edge(0, 1)
            elif phase == 2:
                visible.remove(2)
                blocked.add((0, 1))
            else:
                graph.clear_edges()
                graph.add_edge(1, 2, weight=11)
                visible.add(2)
                blocked.clear()
            assert _view_state(duplicate) == _view_state(view)
            snapshots.append(_view_state(duplicate))
        return snapshots

    assert observe(fnx) == observe(nx)


@pytest.mark.parametrize("cls_name,kind", VIEW_CASES)
def test_shallow_view_copy_does_not_read_filters_or_copy_user_state(cls_name, kind):
    def observe(module):
        _, view, _, _, calls = _live_view(module, cls_name, kind)
        shared = []
        view.extra = shared
        view.self_reference = view
        calls.clear()
        duplicate = copymod.copy(view)
        assert calls == []
        assert duplicate.extra is shared
        assert duplicate.self_reference is view
        duplicate.extra.append("shared")
        duplicate.extra = ["replacement"]
        duplicate.only_on_copy = True
        assert view.extra is shared
        assert not hasattr(view, "only_on_copy")
        return shared, duplicate.extra

    assert observe(fnx) == observe(nx)


@pytest.mark.parametrize("cls_name,kind", VIEW_CASES)
def test_shallow_view_copy_remains_live_when_initially_empty(cls_name, kind):
    def observe(module):
        graph, view, _, _, _ = _live_view(module, cls_name, kind)
        graph.remove_nodes_from(list(graph))
        duplicate = copymod.copy(view)
        assert not duplicate
        assert type(duplicate) is type(view)
        graph.add_edge(0, 1, weight=3)
        assert _view_state(duplicate) == _view_state(view)
        return _view_state(duplicate)

    assert observe(fnx) == observe(nx)


@pytest.mark.parametrize("cls_name", CLASSES)
def test_shallow_view_copy_preserves_subclass_slots_without_initialization(cls_name):
    def observe(module):
        calls = []

        class CustomGraph(getattr(module, cls_name)):
            __slots__ = ("shared_slot", "__private_slot", "unset_slot")

            def __init__(self, required="default"):
                calls.append(required)
                super().__init__()

            def set_private(self, value):
                self.__private_slot = value

            def get_private(self):
                return self.__private_slot

        graph = CustomGraph()
        graph.add_edge(0, 1)
        view = graph.subgraph([0, 1])
        shared = []
        view.shared_slot = shared
        view.set_private(shared)

        def no_init(self, *args, **kwargs):
            raise AssertionError("shallow copying reran subclass initialization")

        CustomGraph.__init__ = no_init
        duplicate = copymod.copy(view)
        assert type(duplicate) is type(view)
        assert duplicate.shared_slot is shared
        assert duplicate.get_private() is shared
        with pytest.raises(AttributeError):
            vars(CustomGraph)["unset_slot"].__get__(duplicate, type(duplicate))
        duplicate.shared_slot = ["replacement"]
        assert view.shared_slot is shared
        graph.add_edge(0, 0)
        assert _view_state(duplicate) == _view_state(view)
        return list(duplicate.edges)

    assert observe(fnx) == observe(nx)


@pytest.mark.parametrize("cls_name", ["DiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("copied", [False, True])
def test_filtered_reverse_edge_lookup_keeps_orientation_and_filters(cls_name, copied):
    def observe(module):
        graph = getattr(module, cls_name)()
        graph.add_edges_from([
            (0, 1, {"weight": 2}), (1, 0, {"weight": 7}), (1, 2, {"weight": 11}),
        ])
        hidden = set()
        view = module.subgraph_view(
            graph.reverse(copy=False),
            filter_edge=lambda u, v, *key: (u, v) not in hidden,
        )
        if copied:
            view = copymod.copy(view)
        results = []
        for blocked in ((), ((1, 0),), ((1, 0), (2, 1))):
            hidden.update(blocked)
            for u, v in ((0, 1), (1, 0), (2, 1), (1, 2), (9, 0)):
                if graph.is_multigraph():
                    for key in (None, 0, "absent"):
                        value = view.get_edge_data(u, v, key, "missing")
                        results.append(dict(value) if value != "missing" else value)
                else:
                    value = view.get_edge_data(u, v, "missing")
                    results.append(dict(value) if value != "missing" else value)
        return results

    assert observe(fnx) == observe(nx)

