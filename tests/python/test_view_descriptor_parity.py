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
import inspect
import pickle

import networkx as nx
import pytest

import franken_networkx as fnx

CLASS_NAMES = ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"]
ACCESSORS = ["nodes", "edges", "degree"]
EDGES = [("n0", "n1"), ("n1", "n2"), ("n2", "n3"), ("n0", "n3"), ("n1", "n1")]


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


@pytest.mark.parametrize("cls_name", CLASS_NAMES)
def test_plain_get_edge_data_is_a_raw_descriptor(cls_name):
    """br-r37-c1-57ba1: ordinary attr reads must not pay a Python shim."""
    graph = _build(fnx, cls_name)
    assert type(graph.get_edge_data).__name__ == "builtin_function_or_method"
    assert graph.get_edge_data("n0", "n1") is not None
    assert graph.get_edge_data("n0", "missing", default="sentinel") == "sentinel"
    assert "get_edge_data" not in vars(graph)


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
        # Existing fnx contract: private NetworkX storage is an ephemeral view
        # override; graph copies serialize the canonical native storage.
        assert list(other) == ["native"]
        assert other.has_node("native")
        assert not other.has_node("private")
        assert other.number_of_nodes() == other.order() == 1
        internal_method_names = {
            "has_node",
            "has_edge",
            "get_edge_data",
            "number_of_nodes",
            "order",
        }
        if cls_name == "DiGraph":
            internal_method_names.update({"neighbors", "successors"})
        assert not internal_method_names & vars(other).keys()


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
