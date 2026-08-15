"""Regression lock for br-r37-c1-wbwkb — the cached non-data view descriptor.

``nodes`` / ``edges`` / ``degree`` are installed by ``_CachedViewDescriptor``, a
NON-data descriptor that memoises the built view under its public attribute name so
repeat access is a C-level instance-dict hit (networkx's own ``@cached_property``
mechanism). These tests pin every contract that mechanism could disturb; they are the
acceptance gate the lever shipped against.

Two of them lock traps that the change actually hit during development:

* ``test_deepcopy_does_not_alias_the_memoised_view`` / ``test_pickle_...`` — the copy
  and ``__reduce_ex__`` paths preserve user instance attributes and skip only
  ``_fnx_``-prefixed keys, so a view memoised under its PUBLIC name was copied to the
  new graph while still bound to the original.
* ``test_subgraph_keeps_its_own_node_view`` — ``_FilteredGraphView.__init__`` sets its
  own ``self.nodes`` and then assigns ``self.adj`` (which routes through
  ``_set_private_override``); an unscoped invalidation there deletes the subgraph's
  node view and exposes the bare ``_FilteredGraphView.nodes`` FUNCTION as a bound
  method.
"""

from __future__ import annotations

import copy
import gc
import inspect
import pickle
import weakref

import networkx as nx
import pytest

import franken_networkx as fnx

CLASS_NAMES = ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"]
ACCESSORS = ["nodes", "edges", "degree"]
DIRECTED_ACCESSORS = ["in_degree", "out_degree", "in_edges", "out_edges"]
EDGES = [("n0", "n1"), ("n1", "n2"), ("n2", "n3"), ("n0", "n3"), ("n1", "n1")]


class _OwnerKey:
    """Identity-hashed Python key which deliberately retains its graph owner."""

    def __init__(self, owner):
        self.owner = owner


def _owner_cycle_reference(graph):
    reference = weakref.ref(graph)
    assert gc.is_tracked(graph)
    return reference


def _assert_reference_collects(reference):
    gc.collect()
    assert reference() is None


def _build(lib, cls_name):
    graph = getattr(lib, cls_name)()
    graph.add_nodes_from([(f"n{i}", {"w": i}) for i in range(4)])
    for left, right in EDGES:
        graph.add_edge(left, right, weight=len(left) + len(right))
    return graph


def _pair(cls_name):
    return _build(nx, cls_name), _build(fnx, cls_name)


@pytest.mark.parametrize("cls_name", CLASS_NAMES)
def test_accessor_content_matches_networkx(cls_name):
    gnx, gfx = _pair(cls_name)
    assert list(gfx.nodes) == list(gnx.nodes)
    assert list(gfx.nodes(data=True)) == list(gnx.nodes(data=True))
    assert list(gfx.edges) == list(gnx.edges)
    assert list(gfx.edges(data=True)) == list(gnx.edges(data=True))
    assert sorted(gfx.degree) == sorted(gnx.degree)


@pytest.mark.parametrize("cls_name", CLASS_NAMES)
@pytest.mark.parametrize("accessor", ACCESSORS)
def test_accessor_identity_type_and_repr_match_networkx(cls_name, accessor):
    """nx's cached_property returns the SAME object on repeat access."""
    gnx, gfx = _pair(cls_name)
    view_a = getattr(gfx, accessor)
    view_b = getattr(gfx, accessor)
    assert view_a is view_b
    assert type(view_a).__name__ == type(getattr(gnx, accessor)).__name__
    assert repr(view_a) == repr(getattr(gnx, accessor))


@pytest.mark.parametrize("cls_name", CLASS_NAMES)
def test_memoised_view_is_live_not_a_snapshot(cls_name):
    gnx, gfx = _pair(cls_name)
    nodes_fx, edges_fx, degree_fx = gfx.nodes, gfx.edges, gfx.degree
    nodes_nx, edges_nx, degree_nx = gnx.nodes, gnx.edges, gnx.degree

    gfx.add_edge("zz", "n0", weight=99)
    gnx.add_edge("zz", "n0", weight=99)
    assert list(nodes_fx) == list(nodes_nx)
    assert list(edges_fx) == list(edges_nx)
    assert sorted(degree_fx) == sorted(degree_nx)

    gfx.remove_node("n2")
    gnx.remove_node("n2")
    assert list(nodes_fx) == list(nodes_nx)
    assert list(edges_fx) == list(edges_nx)
    assert sorted(degree_fx) == sorted(degree_nx)


@pytest.mark.parametrize("cls_name", CLASS_NAMES)
def test_user_assignment_after_cached_view_read_survives_round_trips(cls_name):
    """A user overwrite is state, not the internal view that preceded it."""
    accessors = list(ACCESSORS)
    if "DiGraph" in cls_name:
        accessors.extend(DIRECTED_ACCESSORS)

    for accessor in accessors:
        graph = _build(fnx, cls_name)
        _ = getattr(graph, accessor)
        value = f"user-owned-{accessor}"
        setattr(graph, accessor, value)
        assert accessor not in vars(graph).get("_fnx_descriptor_cached_views", ())

        deep = copy.deepcopy(graph)
        restored = pickle.loads(  # nosec B301  # ubs:ignore - trusted round trip
            pickle.dumps(graph)
        )
        assert getattr(deep, accessor) == value
        assert getattr(restored, accessor) == value


@pytest.mark.parametrize(
    ("cls_name", "accessor"),
    [
        *[
            (cls_name, accessor)
            for cls_name in CLASS_NAMES
            for accessor in (
                "nodes",
                "edges",
                "degree",
                "adj",
                "is_directed",
                "is_multigraph",
            )
        ],
        *[
            (cls_name, accessor)
            for cls_name in ("DiGraph", "MultiDiGraph")
            for accessor in (
                "in_degree",
                "out_degree",
                "in_edges",
                "out_edges",
                "succ",
                "pred",
            )
        ],
    ],
)
def test_cached_accessor_owner_cycle_is_collectable(cls_name, accessor):
    """Cached views and bound predicates must not keep their owner alive."""
    graph = _build(fnx, cls_name)
    reference = weakref.ref(graph)
    getattr(graph, accessor)
    assert gc.is_tracked(graph)

    del graph
    gc.collect()
    assert reference() is None


@pytest.mark.parametrize(
    ("cls_name", "descriptor_name", "subscript"),
    [
        ("Graph", "_GRAPH_ADJ_DESCRIPTOR", False),
        ("Graph", "_GRAPH_ADJ_DESCRIPTOR", True),
        ("DiGraph", "_DIGRAPH_ADJ_DESCRIPTOR", False),
        ("DiGraph", "_DIGRAPH_ADJ_DESCRIPTOR", True),
        ("DiGraph", "_DIGRAPH_PRED_DESCRIPTOR", False),
        ("DiGraph", "_DIGRAPH_PRED_DESCRIPTOR", True),
    ],
)
def test_native_adjacency_view_owner_cycle_is_collectable(
    cls_name, descriptor_name, subscript
):
    """br-r37-c1-5gam7 — the NATIVE adjacency views must not pin their graph.

    The Rust ``Py<Py*Graph>`` handle inside ``AdjacencyView`` / ``AtlasView`` (and
    their directed twins) is invisible to CPython's cyclic collector unless the
    class implements ``__traverse__``, and unbreakable unless it also implements
    ``__clear__``. Both are required: with traverse alone the collector can see
    the cycle but nothing in it can drop a reference.

    The cycle here is the one the ``len(G.adj)`` native-slot migration creates —
    ``_cached_view`` memoises the view by writing straight into ``vars(self)``,
    bypassing the ``__setattr__`` that would otherwise register the instance dict
    for the graph's own ``tp_clear``. All six parametrisations leaked before the
    handle became nullable.
    """
    graph = getattr(fnx, cls_name)()
    graph.add_edge("left", "right")
    view = getattr(fnx, descriptor_name).__get__(graph, type(graph))
    if subscript:
        view = view["left"]

    assert gc.is_tracked(view)
    assert any(referent is graph for referent in gc.get_referents(view))

    vars(graph)["_fnx_native_view_cycle"] = view
    reference = _owner_cycle_reference(graph)
    del graph, view
    _assert_reference_collects(reference)


@pytest.mark.parametrize("cls_name", CLASS_NAMES)
def test_user_instance_attribute_owner_cycle_is_collectable(cls_name):
    graph = getattr(fnx, cls_name)()
    reference = weakref.ref(graph)
    graph.owner = graph
    assert gc.is_tracked(graph)

    del graph
    gc.collect()
    assert reference() is None


@pytest.mark.parametrize("cls_name", CLASS_NAMES)
def test_private_storage_method_shadow_cycle_is_collectable(cls_name):
    graph = getattr(fnx, cls_name)()
    reference = weakref.ref(graph)
    graph._node = {"only": {}}
    assert "has_node" in vars(graph)
    assert gc.is_tracked(graph)

    del graph
    gc.collect()
    assert reference() is None


@pytest.mark.parametrize("cls_name", ["MultiGraph", "MultiDiGraph"])
def test_cached_multigraph_row_owner_cycle_is_collectable(cls_name):
    graph = getattr(fnx, cls_name)()
    graph.add_edge("left", "right")
    reference = weakref.ref(graph)
    graph["left"]
    assert "_fnx_getitem_atlas_cache" in vars(graph)

    del graph
    gc.collect()
    assert reference() is None


@pytest.mark.parametrize("cls_name", CLASS_NAMES)
def test_graph_attribute_self_reference_is_collectable(cls_name):
    graph = getattr(fnx, cls_name)()
    graph.graph["owner"] = graph
    assert graph.graph["owner"] is graph
    reference = _owner_cycle_reference(graph)
    del graph
    _assert_reference_collects(reference)


@pytest.mark.parametrize("cls_name", CLASS_NAMES)
def test_direct_node_attribute_self_reference_is_stored_and_collectable(cls_name):
    graph = getattr(fnx, cls_name)()
    graph.add_node("n", owner=graph)
    assert graph.nodes["n"]["owner"] is graph
    reference = _owner_cycle_reference(graph)
    del graph
    _assert_reference_collects(reference)


@pytest.mark.parametrize("cls_name", CLASS_NAMES)
def test_direct_edge_attribute_self_reference_is_stored_and_collectable(cls_name):
    graph = getattr(fnx, cls_name)()
    graph.add_edge("left", "right", owner=graph)
    if "Multi" in cls_name:
        assert graph["left"]["right"][0]["owner"] is graph
    else:
        assert graph["left"]["right"]["owner"] is graph
    reference = _owner_cycle_reference(graph)
    del graph
    _assert_reference_collects(reference)


@pytest.mark.parametrize("cls_name", CLASS_NAMES)
def test_public_node_key_owner_cycle_is_collectable(cls_name):
    graph = getattr(fnx, cls_name)()
    key = _OwnerKey(graph)
    graph.add_node(key)
    assert next(iter(graph)) is key
    del key
    reference = _owner_cycle_reference(graph)
    del graph
    _assert_reference_collects(reference)


@pytest.mark.parametrize("cls_name", ["MultiGraph", "MultiDiGraph"])
def test_public_multiedge_key_owner_cycle_is_collectable(cls_name):
    graph = getattr(fnx, cls_name)()
    key = _OwnerKey(graph)
    graph.add_edge("left", "right", key=key)
    assert next(iter(graph["left"]["right"])) is key
    del key
    reference = _owner_cycle_reference(graph)
    del graph
    _assert_reference_collects(reference)


@pytest.mark.parametrize(
    ("cls_name", "accessor"),
    [
        ("MultiGraph", "edges"),
        ("DiGraph", "in_edges"),
        ("MultiDiGraph", "in_edges"),
    ],
)
def test_scalar_edge_cache_default_owner_cycle_is_collectable(cls_name, accessor):
    graph = getattr(fnx, cls_name)()
    graph.add_edge("left", "right")
    rows = list(getattr(graph, accessor)(data="missing", default=graph))
    assert rows[0][-1] is graph
    reference = _owner_cycle_reference(graph)
    del rows
    del graph
    _assert_reference_collects(reference)


def test_private_override_installed_after_a_plain_access_redispatches():
    """A graph given networkx private storage must stop serving the plain view."""
    graph = _build(fnx, "Graph")
    plain_type = type(graph.nodes).__name__
    _ = graph.edges
    _ = graph.degree

    graph._node = {"q1": {"tag": 1}, "q2": {"tag": 2}}

    assert sorted(graph.nodes) == ["q1", "q2"]
    assert graph.nodes["q1"] == {"tag": 1}
    assert type(graph.nodes).__name__ != plain_type or sorted(graph.nodes) == ["q1", "q2"]
    assert graph.has_node(n="q1")
    assert not graph.has_node(n="n0")
    assert graph.number_of_nodes() == graph.order() == 2
    assert {"has_node", "number_of_nodes", "order"} <= vars(graph).keys()


@pytest.mark.parametrize("cls_name", CLASS_NAMES)
def test_plain_node_primitives_are_raw_descriptors(cls_name):
    """br-r37-c1-qmi5w: ordinary graphs must not pay a Python shim frame."""
    graph = _build(fnx, cls_name)
    assert type(graph.has_node).__name__ == "builtin_function_or_method"
    assert type(graph.number_of_nodes).__name__ == "builtin_function_or_method"
    assert type(graph.order).__name__ == "builtin_function_or_method"
    assert graph.has_node(n="n0")
    assert graph.number_of_nodes() == graph.order() == 4
    assert not {"has_node", "number_of_nodes", "order"} & vars(graph).keys()


@pytest.mark.parametrize("cls_name", CLASS_NAMES)
def test_plain_has_edge_is_a_raw_descriptor(cls_name):
    """br-r37-c1-6q4wl: ordinary edge probes must not pay a Python shim."""
    graph = _build(fnx, cls_name)
    assert type(graph.has_edge).__name__ == "builtin_function_or_method"
    assert graph.has_edge("n0", "n1")
    assert not graph.has_edge("n0", "missing")
    assert "has_edge" not in vars(graph)


def test_multigraph_has_edge_string_index_cache_is_equal_key_and_mutation_safe():
    """br-r37-c1-paof2: warm exact strings resolve to live native indices."""
    left = "".join(("left", "-", "endpoint"))
    right = "".join(("right", "-", "endpoint"))
    equal_left = left.encode().decode()
    equal_right = right.encode().decode()
    assert equal_left == left and equal_left is not left
    assert equal_right == right and equal_right is not right

    graph = fnx.MultiGraph()
    graph.add_edge(left, right)
    assert graph.has_edge(equal_left, equal_right)
    assert graph.has_edge(equal_left, equal_right)
    assert graph._native_has_edge_uncached_string_control(
        equal_left, equal_right
    )
    assert next(node for node in graph if node == left) is left

    # Edge-only mutations keep node indices stable, so a warm entry stays live.
    graph.remove_edge(left, right)
    assert not graph.has_edge(equal_left, equal_right)
    graph.add_edge(left, right)
    assert graph.has_edge(equal_left, equal_right)

    # Node removal compacts indices; nodes_seq must invalidate both endpoints.
    graph.remove_node(equal_left)
    assert not graph.has_edge(equal_left, equal_right)
    edge_key = "".join(("edge", "-", "key"))
    graph.add_edge(left, right, key=edge_key)
    assert graph.has_edge(equal_left, equal_right)
    equal_key = edge_key.encode().decode()
    assert equal_key is not edge_key
    assert graph.has_edge(equal_left, equal_right, key=equal_key)


def test_multigraph_has_edge_string_index_cache_does_not_alias_copies():
    graph = fnx.MultiGraph()
    graph.add_edge("left", "right")
    assert graph.has_edge("left", "right")  # warm the native-index cache

    copies = (
        copy.copy(graph),
        copy.deepcopy(graph),
        pickle.loads(pickle.dumps(graph)),  # nosec B301  # ubs:ignore - trusted round trip
    )
    graph.remove_edge("left", "right")
    for other in copies:
        assert other.has_edge("left", "right")
        other.remove_node("left")
        assert not other.has_edge("left", "right")
        other.add_edge("left", "right")
        assert other.has_edge("left", "right")


@pytest.mark.parametrize("cls_name", ["Graph", "DiGraph"])
def test_simple_has_edge_string_index_cache_is_equal_key_and_mutation_safe(cls_name):
    """br-r37-c1-p1tvg: simple graphs share the warm string-index route."""
    left = "".join(("left", "-", "endpoint"))
    right = "".join(("right", "-", "endpoint"))
    equal_left = left.encode().decode()
    equal_right = right.encode().decode()
    assert equal_left == left and equal_left is not left
    assert equal_right == right and equal_right is not right

    graph = getattr(fnx, cls_name)()
    graph.add_edge(left, right)
    assert graph.has_edge(equal_left, equal_right)
    assert graph.has_edge(equal_left, equal_right)

    # Edge-only changes retain node indices; a warmed endpoint remains valid.
    graph.remove_edge(left, right)
    assert not graph.has_edge(equal_left, equal_right)
    graph.add_edge(left, right)
    assert graph.has_edge(equal_left, equal_right)

    # Node removal compacts indices, so a warm cache must invalidate first.
    graph.remove_node(equal_left)
    assert not graph.has_edge(equal_left, equal_right)
    graph.add_edge(left, right)
    assert graph.has_edge(equal_left, equal_right)


class _LyingStr(str):
    """A ``str`` subclass whose hash and equality point at a DIFFERENT node.

    The string-index lookaside is a Python dict, so a subclass routed into it
    would be resolved by THESE methods rather than by its characters, and would
    answer for whatever node it claims to equal.
    """

    def __hash__(self):
        return hash("n0")

    def __eq__(self, other):
        return True

    def __ne__(self, other):
        return False


@pytest.mark.parametrize("cls_name", ["Graph", "DiGraph"])
def test_edges_contains_string_route_is_equal_key_and_mutation_safe(cls_name):
    """br-r37-c1-p1tvg: ``(u, v) in G.edges()`` shares the warm string route.

    ``has_edge`` is not this path: the probe enters ``EdgeView.__contains__``,
    so the lookaside has to be wired in here too, under the same contract.
    """
    left = "".join(("left", "-", "endpoint"))
    right = "".join(("right", "-", "endpoint"))
    equal_left = left.encode().decode()
    equal_right = right.encode().decode()
    assert equal_left == left and equal_left is not left
    assert equal_right == right and equal_right is not right

    graph = getattr(fnx, cls_name)()
    reference = getattr(nx, cls_name)()
    for target in (graph, reference):
        target.add_edge(left, right)
        target.add_edge(right, "third")

    # Equal-but-nonidentical keys must hit, warm and cold, exactly as in nx.
    for _ in range(2):
        assert ((equal_left, equal_right) in graph.edges) is True
        assert ((equal_left, equal_right) in reference.edges) is True
    assert ((equal_left, "absent") in graph.edges) is False
    assert ((equal_left, "absent") in reference.edges) is False

    # Edge-only churn keeps node indices; the warm endpoints stay valid.
    graph.remove_edge(left, right)
    reference.remove_edge(left, right)
    assert ((equal_left, equal_right) in graph.edges) is False
    assert ((equal_left, equal_right) in reference.edges) is False
    graph.add_edge(left, right)
    reference.add_edge(left, right)
    assert ((equal_left, equal_right) in graph.edges) is True

    # Node removal renumbers compact indices. A cache that survived it would
    # answer from a stale index — here, "third" now holds the freed slot.
    graph.remove_node(equal_left)
    reference.remove_node(equal_left)
    assert ((equal_left, equal_right) in graph.edges) is False
    assert ((equal_left, equal_right) in reference.edges) is False
    assert ((equal_right, "third") in graph.edges) is True
    graph.add_edge(left, right)
    reference.add_edge(left, right)
    assert ((equal_left, equal_right) in graph.edges) is True
    assert list(graph.edges) == list(reference.edges)


@pytest.mark.parametrize("cls_name", ["Graph", "DiGraph"])
def test_edges_contains_string_route_rejects_str_subclasses(cls_name):
    """A ``str`` subclass must never be resolved by its own hash/eq.

    The fast route is gated on EXACT ``str``. Gate it on ``isinstance``
    instead and ``_LyingStr("absent")`` resolves to ``n0``'s index through the
    dict lookaside, so a nonexistent endpoint reports as present.
    """
    graph = getattr(fnx, cls_name)()
    graph.add_edge("n0", "n1")
    graph.add_edge("n2", "n3")

    # Warm the lookaside so the subclass meets a POPULATED dict.
    assert ("n0", "n1") in graph.edges

    assert (_LyingStr("absent"), "n1") not in graph.edges
    assert ("n0", _LyingStr("absent")) not in graph.edges
    # Subclass keys still resolve by their characters, warm cache or not.
    assert (_LyingStr("n0"), "n1") in graph.edges
    assert (_LyingStr("n2"), _LyingStr("n3")) in graph.edges


def test_directed_edges_contains_string_route_respects_direction():
    """The index route must probe the DIRECTED adjacency, not a mirror."""
    graph = fnx.DiGraph()
    reference = nx.DiGraph()
    for target in (graph, reference):
        target.add_edge("tail", "head")
        target.add_edge("head", "third")

    assert (("tail", "head") in graph.edges) is True
    assert (("head", "tail") in graph.edges) is False
    assert (("head", "tail") in reference.edges) is False
    assert (("tail", "third") in graph.edges) is False
    # Self-loops resolve both endpoints from the same cached entry.
    graph.add_edge("loop", "loop")
    reference.add_edge("loop", "loop")
    assert (("loop", "loop") in graph.edges) is True
    assert list(graph.edges) == list(reference.edges)


@pytest.mark.parametrize("cls_name", CLASS_NAMES)
def test_plain_get_edge_data_is_a_raw_descriptor(cls_name):
    """br-r37-c1-57ba1: ordinary attr reads must not pay a Python shim."""
    graph = _build(fnx, cls_name)
    assert type(graph.get_edge_data).__name__ == "builtin_function_or_method"
    assert graph.get_edge_data("n0", "n1") is not None
    assert graph.get_edge_data("n0", "missing", default="sentinel") == "sentinel"
    assert "get_edge_data" not in vars(graph)


def test_plain_graph_nodeview_contains_is_a_raw_descriptor():
    """br-r37-c1-m7xek: the hash guard lives inside the native C slot."""
    graph = fnx.Graph()
    graph.add_node("present")
    view = graph.nodes
    descriptor = inspect.getattr_static(type(view), "__contains__")

    assert inspect.ismethoddescriptor(descriptor)
    assert "present" in view
    assert "missing" not in view
    with pytest.raises(TypeError, match=r"unhashable type"):
        [] in view


@pytest.mark.parametrize("cls_name", ["Graph", "DiGraph"])
def test_simple_edge_view_getitem_returns_live_native_attr_dict(cls_name):
    """br-r37-c1-sivs2: scalar simple-edge reads bypass mapping wrappers."""
    graph = getattr(fnx, cls_name)()
    graph.add_edge("left", "right", weight=7)
    held_edges = graph.edges

    attrs = held_edges["left", "right"]
    # A repeat is served by the native endpoint lookaside.  The removal below
    # proves the shortcut cannot hand out the stale dict after an edge mutation.
    assert held_edges["left", "right"] is attrs
    assert attrs is graph.get_edge_data("left", "right")
    attrs["color"] = "blue"
    assert graph.get_edge_data("left", "right") == {
        "weight": 7,
        "color": "blue",
    }

    if cls_name == "Graph":
        assert held_edges["right", "left"] is attrs
    else:
        with pytest.raises(KeyError, match="is not in the graph"):
            held_edges["right", "left"]

    graph.remove_edge("left", "right")
    with pytest.raises(KeyError, match="is not in the graph"):
        held_edges["left", "right"]
    graph.add_edge("left", "right", replacement=True)
    assert held_edges["left", "right"] is graph.get_edge_data("left", "right")
    assert held_edges["left", "right"] == {"replacement": True}


@pytest.mark.parametrize("cls_name", ["Graph", "DiGraph"])
def test_held_simple_edge_view_falls_back_after_private_storage_assignment(
    cls_name,
):
    """A held exact-type view must stop reading native storage after override."""
    graph = getattr(fnx, cls_name)()
    graph.add_edge("native-u", "native-v", old=True)
    held_edges = graph.edges
    graph._node = {"private-u": {}, "private-v": {}}

    if cls_name == "Graph":
        graph._adj = {
            "private-u": {"private-v": {"private": True}},
            "private-v": {"private-u": {"private": True}},
        }
    else:
        graph._succ = {
            "private-u": {"private-v": {"private": True}},
            "private-v": {},
        }
        graph._pred = {
            "private-u": {},
            "private-v": {"private-u": {"private": True}},
        }

    assert held_edges["private-u", "private-v"] == {"private": True}
    with pytest.raises(KeyError, match="is not in the graph"):
        held_edges["native-u", "native-v"]


@pytest.mark.parametrize("cls_name", ["Graph", "DiGraph"])
def test_simple_edge_view_subclasses_keep_generic_lookup(cls_name):
    base = getattr(fnx, cls_name)

    class Subclass(base):
        pass

    graph = Subclass()
    graph.add_edge("left", "right", weight=7)
    assert graph.edges["left", "right"] == {"weight": 7}
    if cls_name == "DiGraph":
        assert graph.edges._fnx_native_get_edge_data is None


@pytest.mark.parametrize(
    ("cls_name", "method_name", "node", "expected"),
    [
        ("DiGraph", "neighbors", "n0", ["n1", "n3"]),
        ("DiGraph", "successors", "n0", ["n1", "n3"]),
    ],
)
def test_plain_digraph_neighbor_methods_are_raw_live_iterators(
    cls_name, method_name, node, expected
):
    """br-r37-c1-heyxu: ordinary calls stay in the native descriptor."""
    graph = _build(fnx, cls_name)
    call = getattr(graph, method_name)
    assert type(call).__name__ == "builtin_function_or_method"
    iterator = call(node)
    assert type(iterator).__name__ == "dict_keyiterator"
    assert list(iterator) == expected
    assert method_name not in vars(graph)


@pytest.mark.parametrize(
    ("cls_name", "method_name", "first_edge", "second_edge"),
    [
        ("DiGraph", "successors", ("hub", "first"), ("hub", "second")),
    ],
)
def test_plain_digraph_neighbor_iterators_are_live_and_fail_fast(
    cls_name, method_name, first_edge, second_edge
):
    graph = getattr(fnx, cls_name)()
    graph.add_edge(*first_edge)
    iterator = getattr(graph, method_name)("hub")
    graph.add_edge(*second_edge)
    with pytest.raises(RuntimeError, match="dictionary changed size"):
        next(iterator)
    assert list(getattr(graph, method_name)("hub")) == ["first", "second"]


@pytest.mark.parametrize(
    ("cls_name", "method_name", "row_kind", "expected"),
    [
        ("MultiGraph", "neighbors", "adj", ["n1", "n2", "n3"]),
        ("MultiDiGraph", "neighbors", "succ", ["n1", "n2", "n3"]),
        ("MultiDiGraph", "successors", "succ", ["n1", "n2", "n3"]),
        ("MultiDiGraph", "predecessors", "pred", ["n1", "n2", "n3"]),
    ],
)
def test_multigraph_neighbor_iterators_reuse_key_only_cache(
    cls_name, method_name, row_kind, expected
):
    """br-r37-c1-zrsuc: warm lazy returns must skip list/dict rebuilding."""
    graph = getattr(fnx, cls_name)()
    if method_name == "predecessors":
        graph.add_edges_from((node, "n0") for node in expected)
    else:
        graph.add_edges_from(("n0", node) for node in expected)

    call = getattr(graph, method_name)
    first = call("n0")
    assert type(first).__name__ == "dict_keyiterator"
    assert list(first) == expected

    storage = vars(graph)
    assert storage["_fnx_adj_row_keydict_cache_state"] == (
        graph.nodes_seq,
        graph.edges_seq,
    )
    keydict = storage["_fnx_adj_row_keydict_cache"][(row_kind, "n0")]
    assert list(keydict) == expected
    assert set(keydict.values()) == {None}

    second = call("n0")
    assert type(second).__name__ == "dict_keyiterator"
    assert list(second) == expected
    assert (
        storage["_fnx_adj_row_keydict_cache"][(row_kind, "n0")]
        is keydict
    )


@pytest.mark.parametrize(
    ("cls_name", "method_name", "row_kind"),
    [
        ("MultiGraph", "neighbors", "adj"),
        ("MultiDiGraph", "successors", "succ"),
        ("MultiDiGraph", "predecessors", "pred"),
    ],
)
def test_multigraph_neighbor_key_cache_invalidates_on_mutation(
    cls_name, method_name, row_kind
):
    graph = getattr(fnx, cls_name)()
    if method_name == "predecessors":
        graph.add_edge("n1", "n0")
    else:
        graph.add_edge("n0", "n1")
    call = getattr(graph, method_name)
    assert list(call("n0")) == ["n1"]
    old_keydict = vars(graph)["_fnx_adj_row_keydict_cache"][
        (row_kind, "n0")
    ]

    if method_name == "predecessors":
        graph.add_edge("n2", "n0")
    else:
        graph.add_edge("n0", "n2")
    assert list(call("n0")) == ["n1", "n2"]
    new_keydict = vars(graph)["_fnx_adj_row_keydict_cache"][
        (row_kind, "n0")
    ]
    assert new_keydict is not old_keydict

    if method_name == "predecessors":
        graph.remove_edge("n1", "n0")
    else:
        graph.remove_edge("n0", "n1")
    assert list(call("n0")) == ["n2"]

    graph.remove_node("n2")
    assert list(call("n0")) == []


@pytest.mark.parametrize(
    ("cls_name", "private_attr", "method_name"),
    [
        ("MultiGraph", "_adj", "neighbors"),
        ("MultiDiGraph", "_succ", "successors"),
        ("MultiDiGraph", "_pred", "predecessors"),
    ],
)
def test_multigraph_neighbor_key_cache_defers_to_private_storage(
    cls_name, private_attr, method_name
):
    graph = getattr(fnx, cls_name)()
    graph._node = {"private-u": {}, "private-v": {}}
    setattr(
        graph,
        private_attr,
        {"private-u": {"private-v": {}}, "private-v": {}},
    )

    assert list(getattr(graph, method_name)("private-u")) == ["private-v"]
    assert "_fnx_adj_row_keydict_cache" not in vars(graph)


@pytest.mark.parametrize(
    ("cls_name", "private_attr"),
    [
        ("Graph", "_adj"),
        ("DiGraph", "_succ"),
        ("MultiGraph", "_adj"),
        ("MultiDiGraph", "_succ"),
    ],
)
def test_private_storage_installs_has_edge_instance_shadow(
    cls_name, private_attr
):
    graph = getattr(fnx, cls_name)()
    graph.add_edge("native-u", "native-v")
    graph._node = {"private-u": {}, "private-v": {}}
    row_value = {0: {"weight": 7}} if "Multi" in cls_name else {"weight": 7}
    setattr(
        graph,
        private_attr,
        {
            "private-u": {"private-v": row_value},
            "private-v": {},
        },
    )

    assert graph.has_edge("private-u", "private-v")
    assert not graph.has_edge("native-u", "native-v")
    assert graph.get_edge_data("private-u", "private-v") == row_value
    assert (
        graph.get_edge_data("missing", "private-v", default="sentinel")
        == "sentinel"
    )
    if "Multi" in cls_name:
        assert graph.get_edge_data("private-u", "private-v", key=0) == {
            "weight": 7
        }
    assert type(graph.has_edge).__name__ == "method"
    assert type(graph.get_edge_data).__name__ == "method"
    assert {"has_edge", "get_edge_data"} <= vars(graph).keys()


@pytest.mark.parametrize(
    ("cls_name", "method_name", "private_attr", "rows"),
    [
        (
            "DiGraph",
            "neighbors",
            "_succ",
            {"private-u": {"private-v": {}}, "private-v": {}},
        ),
        (
            "DiGraph",
            "successors",
            "_succ",
            {"private-u": {"private-v": {}}, "private-v": {}},
        ),
    ],
)
def test_private_storage_installs_digraph_neighbor_instance_shadow(
    cls_name, method_name, private_attr, rows
):
    graph = getattr(fnx, cls_name)()
    graph.add_edge("native-u", "native-v")
    graph._node = {"private-u": {}, "private-v": {}}
    setattr(graph, private_attr, rows)

    call = getattr(graph, method_name)
    assert type(call).__name__ == "method"
    assert list(call("private-u")) == ["private-v"]
    assert method_name in vars(graph)
    with pytest.raises(nx.NetworkXError) as error:
        call("missing")
    assert str(error.value) == "The node missing is not in the digraph."


@pytest.mark.parametrize("cls_name", CLASS_NAMES)
def test_node_view_getitem_is_a_raw_descriptor(cls_name):
    """br-r37-c1-yere4: successful lookup must not cross a Python wrapper."""
    gnx, gfx = _pair(cls_name)
    assert not inspect.isfunction(type(gfx.nodes).__getitem__)
    assert gfx.nodes["n0"] is gfx.nodes["n0"]
    assert gfx.nodes["n0"] == gnx.nodes["n0"]


@pytest.mark.parametrize("cls_name", CLASS_NAMES)
def test_node_view_lookup_cache_invalidates_on_remove_and_readd(cls_name):
    gnx, gfx = _pair(cls_name)
    nx_view, fnx_view = gnx.nodes, gfx.nodes
    old_nx, old_fnx = nx_view["n0"], fnx_view["n0"]
    assert fnx_view["n0"] is old_fnx

    gnx.remove_node("n0")
    gfx.remove_node("n0")
    gnx.add_node("n0", generation=2)
    gfx.add_node("n0", generation=2)

    assert fnx_view["n0"] == nx_view["n0"] == {"generation": 2}
    assert fnx_view["n0"] is not old_fnx
    assert nx_view["n0"] is not old_nx


@pytest.mark.parametrize("cls_name", CLASS_NAMES)
def test_node_view_lookup_cache_uses_python_numeric_key_equality(cls_name):
    gnx, gfx = getattr(nx, cls_name)(), getattr(fnx, cls_name)()
    gnx.add_node(1, marker="one")
    gfx.add_node(1, marker="one")
    nx_attrs, fnx_attrs = gnx.nodes[1], gfx.nodes[1]
    for equivalent in (True, 1.0):
        assert gfx.nodes[equivalent] is fnx_attrs
        assert gnx.nodes[equivalent] is nx_attrs


class _EqualNode:
    def __init__(self, value):
        self.value = value

    def __hash__(self):
        return hash(self.value)

    def __eq__(self, other):
        return isinstance(other, _EqualNode) and self.value == other.value

    def __repr__(self):
        return f"_EqualNode({self.value!r})"


@pytest.mark.parametrize("cls_name", CLASS_NAMES)
def test_node_view_lookup_cache_uses_python_object_equality(cls_name):
    gnx, gfx = getattr(nx, cls_name)(), getattr(fnx, cls_name)()
    original = _EqualNode("node")
    equal_query = _EqualNode("node")
    gnx.add_node(original, marker=7)
    gfx.add_node(original, marker=7)
    nx_attrs, fnx_attrs = gnx.nodes[equal_query], gfx.nodes[equal_query]
    assert fnx_attrs == nx_attrs == {"marker": 7}
    assert gfx.nodes[equal_query] is fnx_attrs
    assert gnx.nodes[equal_query] is nx_attrs


@pytest.mark.parametrize("cls_name", CLASS_NAMES)
@pytest.mark.parametrize("key", ["missing", 999, 1.5, True])
def test_node_view_missing_key_keeps_original_key(cls_name, key):
    gnx, gfx = _pair(cls_name)
    with pytest.raises(KeyError) as nx_error:
        gnx.nodes[key]
    with pytest.raises(KeyError) as fnx_error:
        gfx.nodes[key]
    assert fnx_error.value.args == nx_error.value.args == (key,)
    assert fnx_error.value.args[0] is key


@pytest.mark.parametrize("cls_name", CLASS_NAMES)
@pytest.mark.parametrize("key", [[], {}, set()])
def test_node_view_unhashable_key_matches_networkx(cls_name, key):
    gnx, gfx = _pair(cls_name)
    with pytest.raises(TypeError) as nx_error:
        gnx.nodes[key]
    with pytest.raises(TypeError) as fnx_error:
        gfx.nodes[key]
    assert str(fnx_error.value) == str(nx_error.value)


class _UnhashableString(str):
    __hash__ = None


class _ExplodingHash:
    def __hash__(self):
        raise RuntimeError("hash probe reached")


@pytest.mark.parametrize("cls_name", CLASS_NAMES)
@pytest.mark.parametrize(
    ("key", "error_type", "message"),
    [
        (_UnhashableString("n0"), TypeError, "unhashable type"),
        (_ExplodingHash(), RuntimeError, "hash probe reached"),
    ],
    ids=["unhashable-str-subclass", "custom-hash-error"],
)
def test_node_view_subclass_hash_error_is_not_bypassed(
    cls_name, key, error_type, message
):
    gnx, gfx = _pair(cls_name)
    with pytest.raises(error_type, match=message):
        gnx.nodes[key]
    with pytest.raises(error_type, match=message):
        gfx.nodes[key]


@pytest.mark.parametrize("cls_name", CLASS_NAMES)
def test_private_node_method_shadows_do_not_alias_copy_or_pickle(cls_name):
    graph = getattr(fnx, cls_name)()
    graph.add_node("native")
    graph._node = {"private": {"tag": 1}}

    assert graph.has_node("private")
    assert graph.number_of_nodes() == graph.order() == 1

    for other in (
        copy.copy(graph),
        copy.deepcopy(graph),
        pickle.loads(pickle.dumps(graph)),  # nosec B301  # ubs:ignore - trusted round trip
    ):
        # br-r37-c1-s8obc: the clone now reads the assigned mapping, matching
        # networkx 3.6.1 exactly — verified on nx itself, which returns
        # list=['private'], has_node('private')=True, n=1 for all three of these.
        # The previous expectation (['native']) pinned fnx's divergence.
        assert list(other) == ["private"]
        assert other.has_node("private")
        assert not other.has_node("native")
        assert other.number_of_nodes() == other.order() == 1

        # THE POINT OF THIS TEST, unchanged: shadows must not ALIAS the source.
        # Restoring the override necessarily reinstalls the internal shadows on
        # the clone, so their mere presence is no longer the signal — a clone
        # that answers from an assigned mapping needs them. What must never
        # happen is a shadow still bound to the ORIGINAL graph, which is exactly
        # what copying the `_fnx_private_*` keys across verbatim would produce.
        internal_method_names = {
            "has_node",
            "has_edge",
            "get_edge_data",
            "number_of_nodes",
            "order",
        }
        if cls_name == "DiGraph":
            internal_method_names.update({"neighbors", "successors"})
        for name in internal_method_names & vars(other).keys():
            bound_to = getattr(vars(other)[name], "__self__", None)
            assert bound_to is other, f"{name} shadow aliases another graph"
            assert bound_to is not graph


@pytest.mark.parametrize("cls_name", CLASS_NAMES)
def test_native_contains_switches_to_private_node_mapping_and_resets_on_copies(cls_name):
    graph = getattr(fnx, cls_name)()
    graph.add_node("native")

    assert "native" in graph
    assert "missing" not in graph
    assert [] not in graph

    graph._node = {"private": {"tag": 1}}

    assert "private" in graph
    assert "native" not in graph
    assert [] not in graph

    # br-r37-c1-s8obc, RESOLVED for the copy PROTOCOL: `copy.copy`,
    # `copy.deepcopy` and pickle now carry the assigned `_node` exactly as
    # networkx's default `__dict__` copy does, so the mapping survives and the
    # native node does not. Verified against live networkx 3.6.1 on all four
    # classes rather than asserted from fnx alone.
    for other in (copy.copy(graph), copy.deepcopy(graph)):
        assert "private" in other
        assert "native" not in other
        assert [] not in other

    # br-r37-c1-93mx3, RESOLVED: `G.copy()` is networkx's own method rather than
    # part of the copy protocol, and it rebuilds from `self._node` + `self.adj`.
    # This block used to pin fnx's opposite answer (`native` in, `private` out)
    # with a note naming that bead; the bead is fixed, so the pin is flipped to
    # nx parity rather than left asserting a contract that has changed.
    method_copy = graph.copy()
    assert "private" in method_copy
    assert "native" not in method_copy
    assert [] not in method_copy

    # br-r37-c1-w4754: a MATERIALIZED subgraph is a different case, and the old
    # expectation here ("native" in it) contradicted the oracle. Under live networkx
    # 3.6.1, `graph.subgraph(["native"]).copy()` is EMPTY on all four classes: nx's
    # nbunch_iter filters a SEQUENCE nbunch against _adj while the subgraph's node
    # view reads the assigned _node, and those two no longer intersect. fnx now
    # matches by filtering the nbunch against the adjacency mapping whenever private
    # storage is assigned. This assertion was never run against a matching build —
    # the .so installed when it was written predated the native __contains__ flag.
    materialized = graph.subgraph(["native"]).copy()
    assert "native" not in materialized
    assert "private" not in materialized
    assert len(materialized) == 0


def test_private_node_install_preserves_user_instance_methods():
    graph = fnx.Graph()

    def custom(n):
        return n == "sentinel"

    graph.has_node = custom
    graph._node = {"private": {}}

    assert graph.has_node is custom
    assert graph.has_node("sentinel")


def test_private_storage_install_preserves_user_has_edge_method():
    graph = fnx.Graph()

    def custom(u, v):
        return (u, v) == ("sentinel-u", "sentinel-v")

    def custom_data(u, v, default=None):
        if (u, v) == ("sentinel-u", "sentinel-v"):
            return {"custom": True}
        return default

    graph.has_edge = custom
    graph.get_edge_data = custom_data
    graph._adj = {"private-u": {"private-v": {}}}

    assert graph.has_edge is custom
    assert graph.has_edge("sentinel-u", "sentinel-v")
    assert graph.get_edge_data is custom_data
    assert graph.get_edge_data("sentinel-u", "sentinel-v") == {"custom": True}


def test_private_override_state_is_never_memoised():
    graph = _build(fnx, "Graph")
    graph._node = {"z9": {}}
    assert sorted(graph.nodes) == ["z9"]
    assert "nodes" not in vars(graph)


@pytest.mark.parametrize("cls_name", CLASS_NAMES)
def test_subgraph_keeps_its_own_node_view(cls_name):
    """The filtered view sets its own ``nodes`` attribute; it must survive."""
    gnx, gfx = _pair(cls_name)
    sub_fx = gfx.subgraph(["n0", "n1", "n2"])
    sub_nx = gnx.subgraph(["n0", "n1", "n2"])
    # NB: a NodeView is itself callable (``G.nodes(data=True)``), so the failure
    # mode to exclude is specifically a BOUND METHOD leaking through from
    # ``_FilteredGraphView.nodes``.
    assert not inspect.ismethod(sub_fx.nodes), "subgraph node view degraded to a bound method"
    assert list(sub_fx.nodes) == list(sub_nx.nodes)
    assert list(sub_fx.edges) == list(sub_nx.edges)
    assert sorted(sub_fx.degree) == sorted(sub_nx.degree)
    assert sub_fx.has_node("n0") == sub_nx.has_node("n0")
    assert sub_fx.number_of_nodes() == sub_fx.order() == sub_nx.number_of_nodes()


@pytest.mark.parametrize("cls_name", CLASS_NAMES)
def test_edge_subgraph_view(cls_name):
    gnx, gfx = _pair(cls_name)
    sub_fx = gfx.edge_subgraph(list(gfx.edges)[:2])
    sub_nx = gnx.edge_subgraph(list(gnx.edges)[:2])
    assert sorted(sub_fx.nodes) == sorted(sub_nx.nodes)


@pytest.mark.parametrize("cls_name", ["Graph", "MultiGraph"])
def test_copy_does_not_alias_the_memoised_view(cls_name):
    _, gfx = _pair(cls_name)
    _ = gfx.nodes, gfx.edges, gfx.degree
    other = gfx.copy()
    other.add_node("only_in_copy")
    assert "only_in_copy" in other.nodes
    assert "only_in_copy" not in gfx.nodes
    assert other.nodes is not gfx.nodes


@pytest.mark.parametrize("cls_name", ["Graph", "MultiGraph"])
def test_deepcopy_does_not_alias_the_memoised_view(cls_name):
    _, gfx = _pair(cls_name)
    _ = gfx.nodes, gfx.edges, gfx.degree
    other = copy.deepcopy(gfx)
    other.add_node("only_in_deepcopy")
    assert "only_in_deepcopy" in other.nodes
    assert "only_in_deepcopy" not in gfx.nodes


@pytest.mark.parametrize("cls_name", ["Graph", "MultiGraph"])
def test_pickle_round_trip_does_not_alias_the_memoised_view(cls_name):
    _, gfx = _pair(cls_name)
    _ = gfx.nodes, gfx.edges, gfx.degree
    other = pickle.loads(pickle.dumps(gfx))  # nosec B301  # ubs:ignore - trusted round trip
    assert list(other.nodes) == list(gfx.nodes)
    assert list(other.edges) == list(gfx.edges)
    other.add_node("only_in_unpickled")
    assert "only_in_unpickled" in other.nodes
    assert "only_in_unpickled" not in gfx.nodes


def test_user_instance_attributes_still_survive_copy_and_pickle():
    """The descriptor's skip-list must not swallow genuine user attributes."""
    graph = _build(fnx, "Graph")
    graph.custom_attr = 123
    _ = graph.nodes
    assert copy.deepcopy(graph).custom_attr == 123
    assert (
        pickle.loads(pickle.dumps(graph)).custom_attr == 123  # nosec B301  # ubs:ignore - trusted round trip
    )


@pytest.mark.parametrize("accessor", ACCESSORS)
def test_accessor_assignment_matches_networkx(accessor):
    """nx's cached_property is assignable; fnx used to raise AttributeError."""
    gnx, gfx = _pair("Graph")
    setattr(gnx, accessor, "SENTINEL")
    setattr(gfx, accessor, "SENTINEL")
    assert getattr(gfx, accessor) == getattr(gnx, accessor) == "SENTINEL"


def test_graph_adj_public_descriptor_is_cached_and_live():
    """br-r37-c1-pc4hk: repeat access is a dict hit, not a property frame."""
    gnx, gfx = _pair("Graph")
    assert isinstance(fnx.Graph.__dict__["adj"], fnx._CachedViewDescriptor)
    assert "adj" not in vars(gfx)

    nx_view, fnx_view = gnx.adj, gfx.adj
    assert vars(gfx)["adj"] is fnx_view
    assert gfx.adj is fnx_view
    assert {node: dict(row) for node, row in fnx_view.items()} == {
        node: dict(row) for node, row in nx_view.items()
    }

    gnx.add_edge("n0", "later", weight=9)
    gfx.add_edge("n0", "later", weight=9)
    assert list(fnx_view["n0"]) == list(nx_view["n0"])


def test_multigraph_adj_public_descriptor_is_cached_assignable_and_live():
    """MultiGraph gets the same warm instance-dict path as every sibling."""
    gnx, gfx = _pair("MultiGraph")
    assert isinstance(fnx.MultiGraph.__dict__["adj"], fnx._CachedViewDescriptor)
    assert "adj" not in vars(gfx)

    nx_view, fnx_view = gnx.adj, gfx.adj
    assert vars(gfx)["adj"] is fnx_view
    assert gfx.adj is fnx_view
    assert {
        node: {neighbor: list(keys) for neighbor, keys in row.items()}
        for node, row in fnx_view.items()
    } == {
        node: {neighbor: list(keys) for neighbor, keys in row.items()}
        for node, row in nx_view.items()
    }

    gnx.add_edge("n0", "later", key="live", weight=9)
    gfx.add_edge("n0", "later", key="live", weight=9)
    assert list(fnx_view["n0"]["later"]) == list(nx_view["n0"]["later"])

    sub_nx = nx.subgraph_view(gnx, filter_node=lambda node: node != "n1")
    sub_fx = fnx.subgraph_view(gfx, filter_node=lambda node: node != "n1")
    assert list(sub_fx.nodes) == list(sub_nx.nodes)
    assert list(sub_fx.edges(keys=True)) == list(sub_nx.edges(keys=True))

    nx_value = {"public": {"nx": {0: 1}}}
    fnx_value = {"public": {"nx": {0: 1}}}
    gnx.adj = nx_value
    gfx.adj = fnx_value
    assert gfx.adj is fnx_value
    assert "adj" not in vars(gfx).get(fnx._DESCRIPTOR_CACHED_VIEWS, ())
    assert list(gfx.neighbors("n0")) == list(gnx.neighbors("n0"))


def test_graph_adj_user_assignment_clears_internal_cache_marker():
    """A real public value must survive deepcopy/pickle as user state."""
    gnx, gfx = _pair("Graph")
    _ = gnx.adj, gfx.adj
    nx_value = {"public": {"nx": 1}}
    fnx_value = {"public": {"nx": 1}}

    gnx.adj = nx_value
    gfx.adj = fnx_value

    assert gnx.adj is nx_value
    assert gfx.adj is fnx_value
    assert "adj" not in vars(gfx).get(fnx._DESCRIPTOR_CACHED_VIEWS, ())
    # Public assignment does not replace NetworkX's load-bearing ``_adj``;
    # graph methods keep reading the native structure in both libraries.
    assert list(gfx.neighbors("n0")) == list(gnx.neighbors("n0"))
    assert copy.deepcopy(gfx).adj == copy.deepcopy(gnx).adj == fnx_value
    assert (
        pickle.loads(pickle.dumps(gfx)).adj == fnx_value  # nosec B301  # ubs:ignore - trusted round trip
    )


def test_graph_private_adj_assignment_invalidates_public_cache():
    graph = _build(fnx, "Graph")
    old_view = graph.adj
    assigned = {
        "n0": {"n1": {"private": True}},
        "n1": {"n0": {"private": True}},
        "n2": {},
        "n3": {},
    }

    graph._adj = assigned

    assert "adj" not in vars(graph)
    assert graph.adj is assigned
    assert graph.adj is not old_view
    assert list(graph.neighbors("n0")) == ["n1"]


def test_graph_mutation_does_not_cross_public_adj_setattr(monkeypatch):
    """The assignment hook is off the Rust add/remove-edge hot path."""
    graph = fnx.Graph()
    graph.add_nodes_from(("left", "right"))
    raw_setattr = fnx._GRAPH_SETATTR_BEFORE_PUBLIC_ADJ_CACHE
    calls = 0

    def counted_setattr(self, name, value):
        nonlocal calls
        calls += 1
        return raw_setattr(self, name, value)

    monkeypatch.setattr(fnx, "_GRAPH_SETATTR_BEFORE_PUBLIC_ADJ_CACHE", counted_setattr)
    for _ in range(64):
        graph.add_edge("left", "right")
        graph.remove_edge("left", "right")
    assert calls == 0

    graph.user_value = 1
    assert calls == 1


def test_digraph_public_adjacency_descriptors_are_cached_and_live():
    """br-r37-c1-dyuzb: directed warm reads are instance-dict hits."""
    gnx, gfx = _pair("DiGraph")

    for accessor in ("adj", "succ", "pred"):
        assert isinstance(
            fnx.DiGraph.__dict__[accessor], fnx._CachedViewDescriptor
        )
        assert accessor not in vars(gfx)
        nx_view = getattr(gnx, accessor)
        fnx_view = getattr(gfx, accessor)
        assert vars(gfx)[accessor] is fnx_view
        assert getattr(gfx, accessor) is fnx_view
        assert {node: dict(row) for node, row in fnx_view.items()} == {
            node: dict(row) for node, row in nx_view.items()
        }

    gnx.add_edge("later", "n0", weight=9)
    gfx.add_edge("later", "n0", weight=9)
    assert list(gfx.succ["later"]) == list(gnx.succ["later"])
    assert list(gfx.pred["n0"]) == list(gnx.pred["n0"])


@pytest.mark.parametrize("accessor", ["adj", "succ", "pred"])
def test_digraph_public_adjacency_assignment_preserves_private_storage(accessor):
    """A user value shadows only the assignable public cached descriptor."""
    gnx, gfx = _pair("DiGraph")
    _ = getattr(gnx, accessor), getattr(gfx, accessor)
    nx_value = {"public": {"nx": accessor}}
    fnx_value = {"public": {"nx": accessor}}

    setattr(gnx, accessor, nx_value)
    setattr(gfx, accessor, fnx_value)

    assert getattr(gnx, accessor) is nx_value
    assert getattr(gfx, accessor) is fnx_value
    assert accessor not in vars(gfx).get(fnx._DESCRIPTOR_CACHED_VIEWS, ())
    assert list(gfx.edges) == list(gnx.edges)
    assert getattr(copy.deepcopy(gfx), accessor) == fnx_value
    assert (
        getattr(
            pickle.loads(pickle.dumps(gfx)), accessor  # nosec B301  # ubs:ignore - trusted round trip
        )
        == fnx_value
    )


@pytest.mark.parametrize(
    ("private_name", "public_names"),
    [
        ("_adj", ("adj",)),
        ("_succ", ("adj", "succ")),
        ("_pred", ("pred",)),
    ],
)
def test_digraph_private_adjacency_assignment_invalidates_public_caches(
    private_name, public_names
):
    graph = _build(fnx, "DiGraph")
    old_views = {name: getattr(graph, name) for name in ("adj", "succ", "pred")}
    assigned = {"private": {}}

    setattr(graph, private_name, assigned)

    assert all(name not in vars(graph) for name in ("adj", "succ", "pred"))
    for name in public_names:
        assert getattr(graph, name) is assigned
        assert getattr(graph, name) is not old_views[name]


def test_digraph_filtered_and_reverse_views_keep_load_bearing_adjacency():
    """Synthetic empty Rust bases must still install their Python mappings."""
    gnx, gfx = _pair("DiGraph")
    sub_nx = nx.subgraph_view(gnx, filter_node=lambda node: node != "n1")
    sub_fx = fnx.subgraph_view(gfx, filter_node=lambda node: node != "n1")
    reverse_nx = gnx.reverse(copy=False)
    reverse_fx = gfx.reverse(copy=False)

    for nx_view, fnx_view in ((sub_nx, sub_fx), (reverse_nx, reverse_fx)):
        assert list(fnx_view.nodes) == list(nx_view.nodes)
        assert list(fnx_view.edges) == list(nx_view.edges)
        for accessor in ("adj", "succ", "pred"):
            assert {
                node: list(row)
                for node, row in getattr(fnx_view, accessor).items()
            } == {
                node: list(row)
                for node, row in getattr(nx_view, accessor).items()
            }


def test_digraph_mutation_does_not_cross_public_adjacency_setattr(monkeypatch):
    graph = fnx.DiGraph()
    graph.add_nodes_from(("left", "right"))
    raw_setattr = fnx._DIGRAPH_SETATTR_BEFORE_PUBLIC_ADJ_CACHE
    calls = 0

    def counted_setattr(self, name, value):
        nonlocal calls
        calls += 1
        return raw_setattr(self, name, value)

    monkeypatch.setattr(
        fnx, "_DIGRAPH_SETATTR_BEFORE_PUBLIC_ADJ_CACHE", counted_setattr
    )
    for _ in range(64):
        graph.add_edge("left", "right")
        graph.remove_edge("left", "right")
    assert calls == 0

    graph.user_value = 1
    assert calls == 1


def test_multidigraph_public_adjacency_descriptors_are_cached_and_live():
    """br-r37-c1-a5xrj: multi-directed warm reads are instance-dict hits."""
    gnx, gfx = _pair("MultiDiGraph")

    for accessor in ("adj", "succ", "pred"):
        assert isinstance(
            fnx.MultiDiGraph.__dict__[accessor], fnx._CachedViewDescriptor
        )
        assert accessor not in vars(gfx)
        nx_view = getattr(gnx, accessor)
        fnx_view = getattr(gfx, accessor)
        assert vars(gfx)[accessor] is fnx_view
        assert getattr(gfx, accessor) is fnx_view
        assert {
            node: {neighbor: list(keys) for neighbor, keys in row.items()}
            for node, row in fnx_view.items()
        } == {
            node: {neighbor: list(keys) for neighbor, keys in row.items()}
            for node, row in nx_view.items()
        }

    gnx.add_edge("later", "n0", key="live", weight=9)
    gfx.add_edge("later", "n0", key="live", weight=9)
    assert list(gfx.succ["later"]["n0"]) == list(gnx.succ["later"]["n0"])
    assert list(gfx.pred["n0"]["later"]) == list(gnx.pred["n0"]["later"])


@pytest.mark.parametrize(
    ("cls_name", "native_attr"),
    [
        ("MultiGraph", "_MULTIGRAPH_PRIVATE_AWARE_GET_EDGE_DATA"),
        ("MultiDiGraph", "_MULTIDIGRAPH_PRIVATE_AWARE_GET_EDGE_DATA"),
    ],
)
def test_multiedge_keyed_getitem_uses_one_native_lookup(
    cls_name, native_attr, monkeypatch
):
    """br-r37-c1-8l96z: successful scalar lookup bypasses four view layers."""
    gnx, gfx = getattr(nx, cls_name)(), getattr(fnx, cls_name)()
    for graph in (gnx, gfx):
        graph.add_edge("left", "right", key=0, weight=7)

    fnx_edges = gfx.edges
    native = fnx_edges._fnx_native_get_edge_data
    raw_descriptor = getattr(fnx, native_attr)
    assert native is not None
    assert native.__self__ is gfx
    assert native == raw_descriptor.__get__(gfx, type(gfx))

    calls = 0

    def counted_native(*args):
        nonlocal calls
        calls += 1
        return native(*args)

    monkeypatch.setattr(
        fnx_edges, "_fnx_native_get_edge_data", counted_native
    )
    for _ in range(64):
        attrs = fnx_edges["left", "right", 0]
        assert attrs == gnx.edges["left", "right", 0]
        assert attrs is fnx_edges["left", "right", 0]
    assert calls == 128

    attrs["live"] = True
    assert gfx.get_edge_data("left", "right", 0)["live"]


@pytest.mark.parametrize("cls_name", ["MultiGraph", "MultiDiGraph"])
def test_multiedge_keyed_getitem_missing_errors_match_networkx(cls_name):
    gnx, gfx = getattr(nx, cls_name)(), getattr(fnx, cls_name)()
    for graph in (gnx, gfx):
        graph.add_edge("left", "right", key=0, weight=7)

    for edge in (
        ("missing", "right", 0),
        ("left", "missing", 0),
        ("left", "right", 99),
        ("left", "right", None),
        ("left", "right"),
        (["left"], "right", 0),
        ("left", ["right"], 0),
        ("left", "right", []),
    ):
        with pytest.raises(Exception) as nx_error:
            gnx.edges[edge]
        with pytest.raises(type(nx_error.value)) as fnx_error:
            gfx.edges[edge]
        assert fnx_error.value.args == nx_error.value.args


def test_held_multiedge_view_falls_back_after_private_storage_assignment():
    """A held ordinary view must not read stale native storage after ``_adj``."""
    graph = fnx.MultiGraph()
    graph.add_edge(1, 2, key=0, old=True)
    held_edges = graph.edges
    graph._adj = {
        7: {8: {3: {"private": True}}},
        8: {7: {3: {"private": True}}},
    }

    assert held_edges[7, 8, 3] == {"private": True}
    with pytest.raises(KeyError, match="1"):
        held_edges[1, 2, 0]


@pytest.mark.parametrize("cls_name", ["MultiGraph", "MultiDiGraph"])
def test_multiedge_subclasses_keep_generic_keyed_lookup(cls_name):
    base = getattr(fnx, cls_name)

    class Subclass(base):
        pass

    graph = Subclass()
    graph.add_edge("left", "right", key=0, weight=7)
    assert graph.edges._fnx_native_get_edge_data is None
    assert graph.edges["left", "right", 0] == {"weight": 7}


@pytest.mark.parametrize("cls_name", ["MultiGraph", "MultiDiGraph"])
def test_multiedge_identity_int_key_resolution_preserves_numeric_equality(
    cls_name,
):
    """br-r37-c1-d0afg: fast exact-int lookup keeps dict-key equivalence."""
    gnx, gfx = getattr(nx, cls_name)(), getattr(fnx, cls_name)()
    for graph in (gnx, gfx):
        graph.add_edge("left", "right", key=0, weight=7)

    for equivalent_key in (0, False, 0.0):
        assert gfx.edges["left", "right", equivalent_key] == gnx.edges[
            "left", "right", equivalent_key
        ]


@pytest.mark.parametrize("cls_name", ["MultiGraph", "MultiDiGraph"])
def test_multiedge_identity_int_key_resolution_handles_gaps_and_remaps(
    cls_name,
):
    """Gaps use direct membership; one remap conservatively restores scanning."""
    gnx, gfx = getattr(nx, cls_name)(), getattr(fnx, cls_name)()
    for graph in (gnx, gfx):
        graph.add_edge("left", "right", key=0, first=True)
        graph.add_edge("left", "right", key=1, middle=True)
        graph.add_edge("left", "right", key=2, second=True)
        graph.remove_edge("left", "right", key=1)

    assert gfx.edges["left", "right", 2] == gnx.edges["left", "right", 2]
    with pytest.raises(KeyError, match="1"):
        gfx.edges["left", "right", 1]

    for graph in (gnx, gfx):
        graph.add_edge("probe-left", "probe-right", key="remapped")
        graph.remove_edge("probe-left", "probe-right", key="remapped")

    assert gfx.edges["left", "right", 2] == gnx.edges["left", "right", 2]
    for remapped_key in ("missing", -1, 2.5):
        with pytest.raises(KeyError) as nx_error:
            gnx.edges["left", "right", remapped_key]
        with pytest.raises(type(nx_error.value)) as fnx_error:
            gfx.edges["left", "right", remapped_key]
        assert fnx_error.value.args == nx_error.value.args


@pytest.mark.parametrize("accessor", ["adj", "succ", "pred"])
def test_multidigraph_public_adjacency_assignment_preserves_private_storage(
    accessor,
):
    """A user value shadows only the assignable public cached descriptor."""
    gnx, gfx = _pair("MultiDiGraph")
    _ = getattr(gnx, accessor), getattr(gfx, accessor)
    nx_value = {"public": {"nx": accessor}}
    fnx_value = {"public": {"nx": accessor}}

    setattr(gnx, accessor, nx_value)
    setattr(gfx, accessor, fnx_value)

    assert getattr(gnx, accessor) is nx_value
    assert getattr(gfx, accessor) is fnx_value
    assert accessor not in vars(gfx).get(fnx._DESCRIPTOR_CACHED_VIEWS, ())
    assert list(gfx.edges(keys=True)) == list(gnx.edges(keys=True))
    assert getattr(copy.deepcopy(gfx), accessor) == fnx_value
    assert (
        getattr(
            pickle.loads(pickle.dumps(gfx)), accessor  # nosec B301  # ubs:ignore - trusted round trip
        )
        == fnx_value
    )


@pytest.mark.parametrize(
    ("private_name", "public_names"),
    [
        ("_adj", ("adj",)),
        ("_succ", ("adj", "succ")),
        ("_pred", ("pred",)),
    ],
)
def test_multidigraph_private_adjacency_assignment_invalidates_public_caches(
    private_name, public_names
):
    graph = _build(fnx, "MultiDiGraph")
    old_views = {name: getattr(graph, name) for name in ("adj", "succ", "pred")}
    assigned = {"private": {}}

    setattr(graph, private_name, assigned)

    assert all(name not in vars(graph) for name in ("adj", "succ", "pred"))
    for name in public_names:
        assert getattr(graph, name) is assigned
        assert getattr(graph, name) is not old_views[name]


def test_multidigraph_filtered_and_reverse_views_keep_load_bearing_adjacency():
    """Synthetic empty Rust bases must still install their Python mappings."""
    gnx, gfx = _pair("MultiDiGraph")
    sub_nx = nx.subgraph_view(gnx, filter_node=lambda node: node != "n1")
    sub_fx = fnx.subgraph_view(gfx, filter_node=lambda node: node != "n1")
    reverse_nx = gnx.reverse(copy=False)
    reverse_fx = gfx.reverse(copy=False)

    for nx_view, fnx_view in ((sub_nx, sub_fx), (reverse_nx, reverse_fx)):
        assert list(fnx_view.nodes) == list(nx_view.nodes)
        assert list(fnx_view.edges(keys=True)) == list(nx_view.edges(keys=True))
        for accessor in ("adj", "succ", "pred"):
            assert {
                node: {
                    neighbor: list(keys)
                    for neighbor, keys in row.items()
                }
                for node, row in getattr(fnx_view, accessor).items()
            } == {
                node: {
                    neighbor: list(keys)
                    for neighbor, keys in row.items()
                }
                for node, row in getattr(nx_view, accessor).items()
            }


def test_multidigraph_mutation_does_not_cross_public_adjacency_setattr(
    monkeypatch,
):
    graph = fnx.MultiDiGraph()
    graph.add_nodes_from(("left", "right"))
    raw_setattr = fnx._MULTIDIGRAPH_SETATTR_BEFORE_PUBLIC_ADJ_CACHE
    calls = 0

    def counted_setattr(self, name, value):
        nonlocal calls
        calls += 1
        return raw_setattr(self, name, value)

    monkeypatch.setattr(
        fnx, "_MULTIDIGRAPH_SETATTR_BEFORE_PUBLIC_ADJ_CACHE", counted_setattr
    )
    for key in range(64):
        graph.add_edge("left", "right", key=key)
        graph.remove_edge("left", "right", key=key)
    assert calls == 0

    graph.user_value = 1
    assert calls == 1


@pytest.mark.parametrize(
    ("cls_name", "accessors"),
    [
        ("Graph", ("adj",)),
        ("DiGraph", ("adj", "succ", "pred")),
    ],
)
def test_simple_outer_adjacency_len_uses_live_native_count(cls_name, accessors):
    """br-r37-c1-4rgsf: outer views skip the atlas getter, but stay live."""
    gnx, gfx = _pair(cls_name)
    nx_views = [getattr(gnx, name) for name in accessors]
    fnx_views = [getattr(gfx, name) for name in accessors]

    assert all(view._fnx_native_len is not None for view in fnx_views)
    assert [len(view) for view in fnx_views] == [len(view) for view in nx_views]

    gnx.add_node("later")
    gfx.add_node("later")
    assert [len(view) for view in fnx_views] == [len(view) for view in nx_views]

    gnx.remove_node("n1")
    gfx.remove_node("n1")
    assert [len(view) for view in fnx_views] == [len(view) for view in nx_views]


@pytest.mark.parametrize(
    ("cls_name", "accessors"),
    [
        ("Graph", ("adj",)),
        ("DiGraph", ("adj", "succ", "pred")),
    ],
)
def test_simple_outer_adjacency_iter_uses_live_node_mirror(cls_name, accessors):
    """br-r37-c1-krg59: iteration skips atlas materialization, but stays live."""
    gnx, gfx = _pair(cls_name)
    nx_views = [getattr(gnx, name) for name in accessors]
    fnx_views = [getattr(gfx, name) for name in accessors]
    getter_calls = [0] * len(fnx_views)

    for index, view in enumerate(fnx_views):
        old_getter = view._atlas_getter

        def counted_getter(old_getter=old_getter, index=index):
            getter_calls[index] += 1
            return old_getter()

        view._atlas_getter = counted_getter

    assert all(view._fnx_native_iter is not None for view in fnx_views)
    assert [type(iter(view)).__name__ for view in fnx_views] == [
        type(iter(view)).__name__ for view in nx_views
    ]
    assert [list(view) for view in fnx_views] == [list(view) for view in nx_views]
    assert getter_calls == [0] * len(fnx_views)

    gnx.add_node("later")
    gfx.add_node("later")
    assert [list(view) for view in fnx_views] == [list(view) for view in nx_views]
    assert getter_calls == [0] * len(fnx_views)

    gnx.remove_node("n1")
    gfx.remove_node("n1")
    assert [list(view) for view in fnx_views] == [list(view) for view in nx_views]
    assert getter_calls == [0] * len(fnx_views)


@pytest.mark.parametrize(
    ("cls_name", "accessors"),
    [
        ("MultiGraph", ("adj",)),
        ("MultiDiGraph", ("adj", "succ", "pred")),
    ],
)
def test_multi_outer_adjacency_iter_uses_live_node_mirror(cls_name, accessors):
    """br-r37-c1-yisq4: multigraph outer views reuse the node mirror."""
    gnx, gfx = _pair(cls_name)
    nx_views = [getattr(gnx, name) for name in accessors]
    fnx_views = [getattr(gfx, name) for name in accessors]
    getter_calls = [0] * len(fnx_views)

    for index, view in enumerate(fnx_views):
        old_getter = view._atlas_getter

        def counted_getter(old_getter=old_getter, index=index):
            getter_calls[index] += 1
            return old_getter()

        view._atlas_getter = counted_getter

    assert all(view._fnx_native_iter is not None for view in fnx_views)
    assert [type(iter(view)).__name__ for view in fnx_views] == [
        type(iter(view)).__name__ for view in nx_views
    ]
    assert [list(view) for view in fnx_views] == [list(view) for view in nx_views]
    assert getter_calls == [0] * len(fnx_views)

    gnx.add_node("later")
    gfx.add_node("later")
    assert [list(view) for view in fnx_views] == [list(view) for view in nx_views]
    assert getter_calls == [0] * len(fnx_views)

    gnx.remove_node("n1")
    gfx.remove_node("n1")
    assert [list(view) for view in fnx_views] == [list(view) for view in nx_views]
    assert getter_calls == [0] * len(fnx_views)


@pytest.mark.parametrize(
    ("cls_name", "accessors"),
    [
        ("MultiGraph", ("adj",)),
        ("MultiDiGraph", ("adj", "succ", "pred")),
    ],
)
def test_multi_outer_adjacency_contains_uses_native_membership(
    cls_name, accessors
):
    """br-r37-c1-7icpc: membership calls one raw node probe, not the atlas."""
    gnx, gfx = _pair(cls_name)
    nx_views = [getattr(gnx, name) for name in accessors]
    fnx_views = [getattr(gfx, name) for name in accessors]
    getter_calls = [0] * len(fnx_views)
    native_calls = [0] * len(fnx_views)

    for index, view in enumerate(fnx_views):
        old_getter = view._atlas_getter
        old_native_contains = view._fnx_native_contains

        def counted_getter(old_getter=old_getter, index=index):
            getter_calls[index] += 1
            return old_getter()

        def counted_native_contains(
            node, old_native_contains=old_native_contains, index=index
        ):
            native_calls[index] += 1
            return old_native_contains(node)

        view._atlas_getter = counted_getter
        view._fnx_native_contains = counted_native_contains

    assert all(view._fnx_native_contains is not None for view in fnx_views)
    for node in ("n0", "missing"):
        assert [node in view for view in fnx_views] == [
            node in view for view in nx_views
        ]

    calls_before_errors = native_calls.copy()
    for view in nx_views:
        with pytest.raises(TypeError, match="unhashable type: 'list'"):
            [] in view
    for view in fnx_views:
        with pytest.raises(TypeError, match="unhashable type: 'list'"):
            [] in view
    assert native_calls == calls_before_errors

    gnx.add_node("later")
    gfx.add_node("later")
    assert ["later" in view for view in fnx_views] == [
        "later" in view for view in nx_views
    ]

    gnx.remove_node("n1")
    gfx.remove_node("n1")
    assert ["n1" in view for view in fnx_views] == [
        "n1" in view for view in nx_views
    ]
    assert getter_calls == [0] * len(fnx_views)
    assert native_calls == [4] * len(fnx_views)


@pytest.mark.parametrize("cls_name", ["Graph", "DiGraph"])
def test_simple_adjacency_iter_keeps_native_storage_under_node_override(cls_name):
    """An independent ``_node`` assignment must not change adjacency keys."""
    gnx, gfx = _pair(cls_name)
    old_nx, old_fnx = gnx.adj, gfx.adj

    gnx._node = {"private-only": {}}
    gfx._node = {"private-only": {}}

    assert list(old_fnx) == list(old_nx)
    assert list(gfx.adj) == list(gnx.adj) == list(old_nx)
    assert list(gfx) == list(gnx) == ["private-only"]


@pytest.mark.parametrize("cls_name", ["MultiGraph", "MultiDiGraph"])
def test_multi_adjacency_iter_keeps_native_storage_under_node_override(cls_name):
    gnx, gfx = _pair(cls_name)
    old_nx, old_fnx = gnx.adj, gfx.adj

    gnx._node = {"private-only": {}}
    gfx._node = {"private-only": {}}

    assert list(old_fnx) == list(old_nx)
    assert list(gfx.adj) == list(gnx.adj) == list(old_nx)
    assert list(gfx) == list(gnx) == ["private-only"]


@pytest.mark.parametrize("cls_name", ["MultiGraph", "MultiDiGraph"])
def test_multi_adjacency_contains_keeps_native_storage_under_node_override(
    cls_name,
):
    gnx, gfx = _pair(cls_name)
    old_nx, old_fnx = gnx.adj, gfx.adj

    gnx._node = {"private-only": {}}
    gfx._node = {"private-only": {}}

    assert "n0" in old_fnx
    assert ("n0" in old_fnx) == ("n0" in old_nx)
    assert "private-only" not in old_fnx
    assert ("private-only" in old_fnx) == ("private-only" in old_nx)
    assert "n0" in gfx.adj
    assert ("n0" in gfx.adj) == ("n0" in gnx.adj)
    assert "private-only" in gfx
    assert ("private-only" in gfx) == ("private-only" in gnx)


@pytest.mark.parametrize("cls_name", ["Graph", "DiGraph"])
def test_simple_adjacency_iter_preserves_size_change_error(cls_name):
    gnx, gfx = _pair(cls_name)
    nx_iterator = iter(gnx.adj)
    fnx_iterator = iter(gfx.adj)
    assert next(fnx_iterator) == next(nx_iterator)

    gnx.add_node("size-change")
    gfx.add_node("size-change")

    with pytest.raises(RuntimeError, match="dictionary changed size during iteration"):
        next(nx_iterator)
    with pytest.raises(RuntimeError, match="dictionary changed size during iteration"):
        next(fnx_iterator)


@pytest.mark.parametrize("cls_name", ["MultiGraph", "MultiDiGraph"])
def test_multi_adjacency_iter_preserves_size_change_error(cls_name):
    gnx, gfx = _pair(cls_name)
    nx_iterator = iter(gnx.adj)
    fnx_iterator = iter(gfx.adj)
    assert next(fnx_iterator) == next(nx_iterator)

    gnx.add_node("size-change")
    gfx.add_node("size-change")

    with pytest.raises(RuntimeError, match="dictionary changed size during iteration"):
        next(nx_iterator)
    with pytest.raises(RuntimeError, match="dictionary changed size during iteration"):
        next(fnx_iterator)


@pytest.mark.parametrize("cls_name", ["Graph", "DiGraph"])
def test_simple_adjacency_len_keeps_native_storage_under_node_override(cls_name):
    """An independent ``_node`` assignment must not change adjacency length."""
    gnx, gfx = _pair(cls_name)
    old_nx, old_fnx = gnx.adj, gfx.adj
    native_count = len(old_nx)

    gnx._node = {"private-only": {}}
    gfx._node = {"private-only": {}}

    assert gnx.number_of_nodes() == gfx.number_of_nodes() == 1
    assert len(old_fnx) == len(old_nx) == native_count
    assert len(gfx.adj) == len(gnx.adj) == native_count


def test_adjacency_len_without_native_owner_uses_live_mapping_fallback():
    snapshot = {"left": {}, "right": {}}
    view = fnx.AdjacencyView(lambda: snapshot)
    assert view._fnx_native_len is None
    assert view._fnx_native_iter is None
    assert len(view) == 2
    assert list(view) == ["left", "right"]
    snapshot["later"] = {}
    assert len(view) == 3
    assert list(view) == ["left", "right", "later"]


def test_multi_adjacency_iter_without_native_owner_uses_live_mapping_fallback():
    snapshot = {"left": {}, "right": {}}
    view = fnx.MultiAdjacencyView(lambda: snapshot)
    assert view._fnx_native_iter is None
    assert view._fnx_native_contains is None
    assert list(view) == ["left", "right"]
    assert "left" in view
    assert "missing" not in view
    snapshot["later"] = {}
    assert list(view) == ["left", "right", "later"]
    assert "later" in view


DIRECTED_ACCESSORS = ["in_degree", "out_degree", "in_edges", "out_edges"]


@pytest.mark.parametrize("cls_name", ["DiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("accessor", DIRECTED_ACCESSORS)
def test_directed_accessor_identity_matches_networkx(cls_name, accessor):
    """br-r37-c1-hwu8a: nx caches all four; fnx's edge views used to rebuild.

    ``G.out_edges is G.out_edges`` was False under the old per-access
    ``property`` getter while nx's ``cached_property`` makes it True.
    """
    gnx, gfx = _pair(cls_name)
    assert (getattr(gfx, accessor) is getattr(gfx, accessor)) is (
        getattr(gnx, accessor) is getattr(gnx, accessor)
    )
    assert type(getattr(gfx, accessor)).__name__ == type(getattr(gnx, accessor)).__name__


@pytest.mark.parametrize("cls_name", ["DiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("accessor", DIRECTED_ACCESSORS)
def test_directed_accessor_content_matches_networkx(cls_name, accessor):
    gnx, gfx = _pair(cls_name)
    assert sorted(map(str, getattr(gfx, accessor))) == sorted(map(str, getattr(gnx, accessor)))
    assert len(getattr(gfx, accessor)) == len(getattr(gnx, accessor))


@pytest.mark.parametrize("cls_name", ["DiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("accessor", DIRECTED_ACCESSORS)
def test_directed_accessor_view_is_live(cls_name, accessor):
    """A memoised edge/degree view must observe later mutation."""
    gnx, gfx = _pair(cls_name)
    view_fx, view_nx = getattr(gfx, accessor), getattr(gnx, accessor)
    gfx.add_edge("fresh_u", "fresh_v", weight=3)
    gnx.add_edge("fresh_u", "fresh_v", weight=3)
    assert sorted(map(str, view_fx)) == sorted(map(str, view_nx))
    gfx.remove_node("n1")
    gnx.remove_node("n1")
    assert sorted(map(str, view_fx)) == sorted(map(str, view_nx))


@pytest.mark.parametrize("cls_name", ["DiGraph", "MultiDiGraph"])
def test_directed_accessor_copy_is_not_aliased(cls_name):
    _, gfx = _pair(cls_name)
    for accessor in DIRECTED_ACCESSORS:
        getattr(gfx, accessor)
    other = copy.deepcopy(gfx)
    other.add_edge("only_u", "only_v")
    assert ("only_u", "only_v") in {(u, v) for u, v, *_ in other.out_edges}
    assert ("only_u", "only_v") not in {(u, v) for u, v, *_ in gfx.out_edges}


@pytest.mark.parametrize("cls_name", CLASS_NAMES)
def test_randomized_mutation_differential(cls_name):
    """Accessor surface stays byte-identical to nx across mutation sequences."""
    import random

    rng = random.Random(hash(cls_name) & 0xFFFF)
    for trial in range(8):
        gnx, gfx = getattr(nx, cls_name)(), getattr(fnx, cls_name)()
        for _ in range(40):
            left, right = str(rng.randrange(12)), str(rng.randrange(12))
            weight = rng.randint(1, 9)
            gnx.add_edge(left, right, weight=weight)
            gfx.add_edge(left, right, weight=weight)
        for step in range(6):
            node = str(rng.randrange(12))
            if node in gnx:
                gnx.nodes[node]["mark"] = step
                gfx.nodes[node]["mark"] = step
        if trial % 3 == 0 and len(gnx) > 3:
            victim = list(gnx)[1]
            gnx.remove_node(victim)
            gfx.remove_node(victim)
        assert list(gfx.nodes(data=True)) == list(gnx.nodes(data=True))
        assert list(gfx.edges(data=True)) == list(gnx.edges(data=True))
        assert sorted(gfx.degree) == sorted(gnx.degree)
        assert {k: dict(v) for k, v in gfx.adjacency()} == {
            k: dict(v) for k, v in gnx.adjacency()
        }


# ---------------------------------------------------------------------------
# `(u, v) in G.edges()` — endpoint-resolution coverage.
#
# Written for br-r37-c1-p1tvg, which proposed resolving exact-`str` endpoints
# through the node-index lookaside instead of rebuilding a canonical key per
# endpoint. That lever was measured and REVERTED (1.27x slower despite -101
# Ir/call; see the comment in views.rs). The coverage outlives it: this probe
# had no direct differential tests, and these are what would catch a future
# attempt that changes the ANSWER rather than only the cost.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("cls_name", ["Graph", "DiGraph"])
def test_edge_view_contains_matches_networkx_for_string_endpoints(cls_name):
    gnx, gfx = _pair(cls_name)
    probes = [
        ("n0", "n1"),
        ("n1", "n0"),
        ("n1", "n1"),
        ("n0", "n2"),
        ("n0", "missing"),
        ("missing", "n0"),
        ("missing", "other"),
    ]
    for probe in probes:
        assert (probe in gfx.edges) == (probe in gnx.edges), probe


@pytest.mark.parametrize("cls_name", ["Graph", "DiGraph"])
def test_edge_view_contains_hits_on_equal_but_nonidentical_strings(cls_name):
    """Endpoint resolution must be by VALUE, never by object identity."""
    gnx, gfx = _pair(cls_name)
    view_fx, view_nx = gfx.edges, gnx.edges
    assert ("n0", "n1") in view_fx  # probe once with interned literals
    # Built at runtime, so these are equal to but not the same object as the
    # keys the graph holds; `"".join` defeats the compiler's literal interning.
    left, right = "".join(["n", "0"]), "".join(["n", "1"])
    held = next(n for n in gfx.nodes if n == "n0")
    assert left == held and left is not held  # equal, distinct object
    assert (left, right) in view_fx
    assert ((left, right) in view_fx) == ((left, right) in view_nx)


@pytest.mark.parametrize("cls_name", ["Graph", "DiGraph"])
def test_edge_view_contains_tracks_node_removal_and_readd(cls_name):
    """Removal renumbers compact node indices, so any endpoint memo keyed on
    them must be invalidated. Pinned live because that is the failure a cache
    would introduce silently."""
    gnx, gfx = _pair(cls_name)
    view_fx, view_nx = gfx.edges, gnx.edges
    assert ("n0", "n1") in view_fx
    assert ("n1", "n2") in view_fx
    for graph in (gnx, gfx):
        graph.remove_node("n0")
    assert (("n0", "n1") in view_fx) == (("n0", "n1") in view_nx) is False
    assert (("n1", "n2") in view_fx) == (("n1", "n2") in view_nx) is True
    for graph in (gnx, gfx):
        graph.add_node("n0")
    # Re-added with no edges: present as a node, still not an endpoint.
    assert (("n0", "n1") in view_fx) == (("n0", "n1") in view_nx) is False
    for graph in (gnx, gfx):
        graph.add_edge("n0", "n1")
    assert (("n0", "n1") in view_fx) == (("n0", "n1") in view_nx) is True


class _CaseInsensitiveStr(str):
    def __eq__(self, other):
        return str(self).lower() == str(other).lower()

    def __hash__(self):
        return hash(str(self).lower())


@pytest.mark.parametrize("cls_name", ["Graph", "DiGraph"])
def test_edge_view_contains_str_subclass_keeps_the_canonical_path(cls_name):
    """A `str` SUBCLASS may override `__hash__`/`__eq__`, so any endpoint fast
    path must gate on `is_exact_instance_of`, never `isinstance`.

    A PLAIN subclass has str's own hash and equality, so the canonical path
    gives nx's answer and this is a true parity assertion. The overriding
    subclasses are NOT asserted against nx here: fnx already diverges from nx
    on those, pre-existing, tracked in br-r37-c1-lvlu7. What is asserted about
    them is that the answer is whatever the canonical path yields.
    """
    gnx, gfx = _pair(cls_name)

    class _Plain(str):
        pass

    for probe in [(_Plain("n0"), "n1"), ("n0", _Plain("n1")), (_Plain("zz"), "n1")]:
        assert (probe in gfx.edges) == (probe in gnx.edges), probe

    # Subclass with a custom equivalence: the canonical path compares BYTES, so
    # "N0" does not reach node "n0". Pinning it here is what would fail loudly
    # if the gate were ever widened to `isinstance`.
    assert (_CaseInsensitiveStr("N0"), "n1") not in gfx.edges
    assert (_CaseInsensitiveStr("n0"), "n1") in gfx.edges


@pytest.mark.parametrize("cls_name", ["Graph", "DiGraph"])
def test_edge_view_contains_non_string_endpoints_match_networkx(cls_name):
    """Mixed and non-str endpoints fall through to the canonical path."""
    gnx, gfx = getattr(nx, cls_name)(), getattr(fnx, cls_name)()
    for graph in (gnx, gfx):
        graph.add_edge(1, 2)
        graph.add_edge("1", "2")
    for probe in [(1, 2), ("1", "2"), (1, "2"), ("1", 2), (2, 1), (1, 3)]:
        assert (probe in gfx.edges) == (probe in gnx.edges), probe
