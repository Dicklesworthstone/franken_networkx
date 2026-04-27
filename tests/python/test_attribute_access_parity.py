"""Parity coverage for graph attribute helper wrappers."""

import networkx as nx
import pytest

import franken_networkx as fnx


def test_set_node_attributes_dict_with_name():
    graph = fnx.path_graph(3)
    expected = nx.path_graph(3)

    values = {0: "red", 1: "blue", 99: "ignored"}
    fnx.set_node_attributes(graph, values, "color")
    nx.set_node_attributes(expected, values, "color")

    assert dict(graph.nodes(data=True)) == dict(expected.nodes(data=True))


def test_set_node_attributes_dict_of_dicts():
    graph = fnx.Graph()
    graph.add_nodes_from([0, 1])
    expected = nx.Graph()
    expected.add_nodes_from([0, 1])

    values = {0: {"color": "red", "size": 5}, 4: {"ignored": True}}
    fnx.set_node_attributes(graph, values)
    nx.set_node_attributes(expected, values)

    assert dict(graph.nodes(data=True)) == dict(expected.nodes(data=True))


def test_set_node_attributes_scalar_broadcast():
    graph = fnx.path_graph(4)
    expected = nx.path_graph(4)

    fnx.set_node_attributes(graph, "default", "label")
    nx.set_node_attributes(expected, "default", "label")

    assert dict(graph.nodes(data=True)) == dict(expected.nodes(data=True))


def test_get_node_attributes_excludes_missing_when_default_is_none():
    graph = fnx.Graph()
    graph.add_node("a", color="red")
    graph.add_node("b")
    expected = nx.Graph()
    expected.add_node("a", color="red")
    expected.add_node("b")

    assert fnx.get_node_attributes(graph, "color", default=None) == nx.get_node_attributes(
        expected,
        "color",
        default=None,
    )


def test_get_node_attributes_includes_default_for_missing_nodes():
    graph = fnx.Graph()
    graph.add_node("a", color="red")
    graph.add_node("b")
    expected = nx.Graph()
    expected.add_node("a", color="red")
    expected.add_node("b")

    assert fnx.get_node_attributes(graph, "color", default="missing") == nx.get_node_attributes(
        expected,
        "color",
        default="missing",
    )


def test_set_edge_attributes_dict_with_name():
    graph = fnx.Graph()
    graph.add_edge(0, 1)
    graph.add_edge(1, 2)
    expected = nx.Graph()
    expected.add_edge(0, 1)
    expected.add_edge(1, 2)

    values = {(1, 0): 7, (2, 9): 11}
    fnx.set_edge_attributes(graph, values, "weight")
    nx.set_edge_attributes(expected, values, "weight")

    assert sorted(graph.edges(data=True)) == sorted(expected.edges(data=True))


def test_set_edge_attributes_dict_of_dicts():
    graph = fnx.Graph()
    graph.add_edge("a", "b")
    expected = nx.Graph()
    expected.add_edge("a", "b")

    values = {("a", "b"): {"weight": 3, "color": "red"}, ("x", "y"): {"ignored": True}}
    fnx.set_edge_attributes(graph, values)
    nx.set_edge_attributes(expected, values)

    assert sorted(graph.edges(data=True)) == sorted(expected.edges(data=True))


def test_set_edge_attributes_scalar_broadcast():
    graph = fnx.path_graph(4)
    expected = nx.path_graph(4)

    fnx.set_edge_attributes(graph, 9, "weight")
    nx.set_edge_attributes(expected, 9, "weight")

    assert sorted(graph.edges(data=True)) == sorted(expected.edges(data=True))


def test_get_edge_attributes_multigraph_preserves_keys_and_defaults():
    graph = fnx.MultiGraph()
    graph.add_edge("a", "b", key=7, weight=3)
    graph.add_edge("a", "b", key=8)
    expected = nx.MultiGraph()
    expected.add_edge("a", "b", key=7, weight=3)
    expected.add_edge("a", "b", key=8)

    assert fnx.get_edge_attributes(graph, "weight", default=0) == nx.get_edge_attributes(
        expected,
        "weight",
        default=0,
    )


def test_set_edge_attributes_multigraph_matches_networkx():
    graph = fnx.MultiGraph()
    graph.add_edge("a", "b", key=7)
    graph.add_edge("a", "b", key=8)
    expected = nx.MultiGraph()
    expected.add_edge("a", "b", key=7)
    expected.add_edge("a", "b", key=8)

    values = {("b", "a", 7): {"weight": 5, "color": "red"}, ("a", "b", 9): {"ignored": True}}
    fnx.set_edge_attributes(graph, values)
    nx.set_edge_attributes(expected, values)

    assert sorted(graph.edges(keys=True, data=True)) == sorted(expected.edges(keys=True, data=True))


def test_attribute_roundtrip_matches_networkx_on_directed_multigraph():
    graph = fnx.MultiDiGraph()
    graph.add_edge("u", "v", key=1)
    graph.add_edge("v", "u", key=2)
    graph.add_node("u")
    graph.add_node("v")

    expected = nx.MultiDiGraph()
    expected.add_edge("u", "v", key=1)
    expected.add_edge("v", "u", key=2)
    expected.add_node("u")
    expected.add_node("v")

    fnx.set_node_attributes(graph, {"u": {"role": "source"}, "v": {"role": "sink"}})
    nx.set_node_attributes(expected, {"u": {"role": "source"}, "v": {"role": "sink"}})
    fnx.set_edge_attributes(graph, {("u", "v", 1): 2, ("v", "u", 2): 4}, "weight")
    nx.set_edge_attributes(expected, {("u", "v", 1): 2, ("v", "u", 2): 4}, "weight")

    assert fnx.get_node_attributes(graph, "role") == nx.get_node_attributes(expected, "role")
    assert fnx.get_edge_attributes(graph, "weight") == nx.get_edge_attributes(expected, "weight")


def test_multidigraph_edges_keys_view_matches_networkx():
    graph = fnx.MultiDiGraph()
    expected = nx.MultiDiGraph()
    for target_graph in (graph, expected):
        target_graph.add_edge("a", "b", key="k1", weight=1)
        target_graph.add_edge("a", "b", key="k2", weight=2)
        target_graph.add_edge("b", "a", key="k3")

    assert list(graph.edges("a", keys=True)) == list(expected.edges("a", keys=True))
    assert list(graph.edges(nbunch=["a"], keys=True)) == list(
        expected.edges(nbunch=["a"], keys=True)
    )
    assert list(graph.edges(["a"], data=True, keys=True)) == list(
        expected.edges(["a"], data=True, keys=True)
    )
    assert list(graph.edges(data="weight", keys=True, default=99)) == list(
        expected.edges(data="weight", keys=True, default=99)
    )
    assert list(graph.edges(["z", "a"], data="weight", keys=True, default=99)) == list(
        expected.edges(["z", "a"], data="weight", keys=True, default=99)
    )
    assert list(graph.edges(["z"], keys=True)) == list(expected.edges(["z"], keys=True))

    try:
        list(expected.edges(1, keys=True))
    except Exception as exc:
        expected_exc = exc
    else:
        raise AssertionError("expected NetworkX MultiDiGraph.edges(1, keys=True) to fail")

    fnx_exc_type = getattr(fnx, type(expected_exc).__name__)
    with pytest.raises(fnx_exc_type, match=str(expected_exc)):
        list(graph.edges(1, keys=True))


@pytest.mark.parametrize(
    ("fnx_factory", "nx_factory"),
    [
        (fnx.MultiGraph, nx.MultiGraph),
        (fnx.MultiDiGraph, nx.MultiDiGraph),
    ],
)
def test_non_integer_multigraph_edge_keys_roundtrip_matches_networkx(
    fnx_factory,
    nx_factory,
):
    graph = fnx_factory()
    expected = nx_factory()
    key = ("left", "right")

    assert graph.add_edge("a", "b", key=key, weight=3) == expected.add_edge(
        "a",
        "b",
        key=key,
        weight=3,
    )
    assert graph.has_edge("a", "b", key=key) == expected.has_edge("a", "b", key=key)
    assert graph.get_edge_data("a", "b", key=key) == expected.get_edge_data("a", "b", key=key)
    assert dict(graph["a"]["b"]) == dict(expected["a"]["b"])
    assert list(graph.edges(keys=True, data=True)) == list(expected.edges(keys=True, data=True))

    copied = graph.copy()
    expected_copied = expected.copy()
    assert list(copied.edges(keys=True, data=True)) == list(
        expected_copied.edges(keys=True, data=True)
    )

    subgraph = graph.edge_subgraph([("a", "b", key)])
    expected_subgraph = expected.edge_subgraph([("a", "b", key)]).copy()
    assert list(subgraph.edges(keys=True, data=True)) == list(
        expected_subgraph.edges(keys=True, data=True)
    )

    graph.remove_edge("a", "b", key=key)
    expected.remove_edge("a", "b", key=key)
    assert list(graph.edges(keys=True, data=True)) == list(expected.edges(keys=True, data=True))


def test_matches_networkx_on_mixed_attribute_workflow():
    graph = fnx.Graph()
    graph.add_edges_from([(0, 1), (1, 2), (2, 3)])
    graph.add_nodes_from([4, 5])
    expected = nx.Graph()
    expected.add_edges_from([(0, 1), (1, 2), (2, 3)])
    expected.add_nodes_from([4, 5])

    fnx.set_node_attributes(graph, {0: "red", 2: "blue"}, "color")
    nx.set_node_attributes(expected, {0: "red", 2: "blue"}, "color")
    fnx.set_node_attributes(graph, {1: {"size": 5}, 4: {"size": 9}})
    nx.set_node_attributes(expected, {1: {"size": 5}, 4: {"size": 9}})
    fnx.set_edge_attributes(graph, {(0, 1): 2, (2, 1): 5}, "weight")
    nx.set_edge_attributes(expected, {(0, 1): 2, (2, 1): 5}, "weight")

    assert dict(graph.nodes(data=True)) == dict(expected.nodes(data=True))
    assert sorted(graph.edges(data=True)) == sorted(expected.edges(data=True))
    assert fnx.get_node_attributes(graph, "color", default="missing") == nx.get_node_attributes(
        expected,
        "color",
        default="missing",
    )
    assert fnx.get_edge_attributes(graph, "weight", default=0) == nx.get_edge_attributes(
        expected,
        "weight",
        default=0,
    )


@pytest.mark.parametrize(
    "fnx_cls",
    [fnx.MultiGraph, fnx.MultiDiGraph],
)
def test_multigraph_copy_preserves_edge_attribute_named_key(fnx_cls):
    """Regression guard for franken_networkx-9x7r0.

    MultiGraph / MultiDiGraph copy used to call
    ``add_edge(u, v, key=key, **attrs)`` which collides with
    ``TypeError: got multiple values for keyword argument 'key'`` when
    an edge attribute is literally named ``'key'``. Same pattern for
    to_undirected on MultiGraph and for the view-class copies.
    """
    g = fnx_cls()
    g.add_edge("a", "b", weight=10)
    # Attribute literally named "key"
    g["a"]["b"][0]["key"] = "stored_value"

    copy = g.copy()
    edges = list(copy.edges(keys=True, data=True))
    assert edges == [("a", "b", 0, {"weight": 10, "key": "stored_value"})]


def test_multigraph_to_undirected_preserves_edge_attribute_named_key():
    """Regression guard for franken_networkx-9x7r0 on the
    ``MultiGraph.to_undirected`` path (not ``MultiDiGraph``, which goes
    through ``_directed_to_undirected_with_view``'s already-correct
    ``add_edges_from`` form).
    """
    g = fnx.MultiGraph()
    g.add_edge("a", "b", weight=5)
    g["a"]["b"][0]["key"] = "stored"

    u = g.to_undirected()
    edges = list(u.edges(keys=True, data=True))
    assert edges == [("a", "b", 0, {"weight": 5, "key": "stored"})]


# ---------------------------------------------------------------------------
# franken_networkx-3ehfp: graph-returning delegated exports must return fnx
# graphs, not nx graphs (round-trip through readwrite._from_nx_graph).
# ---------------------------------------------------------------------------


def test_bfs_tree_returns_fnx_digraph():
    g = fnx.Graph()
    g.add_edges_from([(0, 1), (1, 2), (2, 3)])
    tree = fnx.bfs_tree(g, 0)
    assert isinstance(tree, fnx.DiGraph)
    assert sorted(tree.edges()) == [(0, 1), (1, 2), (2, 3)]


def test_random_tournament_returns_fnx_digraph():
    tournament = fnx.random_tournament(5, seed=42)
    assert isinstance(tournament, fnx.DiGraph)
    assert tournament.number_of_nodes() == 5


@pytest.mark.parametrize(
    "fnx_cls",
    [fnx.Graph, fnx.DiGraph, fnx.MultiGraph, fnx.MultiDiGraph],
)
def test_union_with_rename_returns_fnx_graph(fnx_cls):
    g = fnx_cls()
    h = fnx_cls()
    g.add_edge("a", "b")
    h.add_edge("c", "d")

    combined = fnx.union(g, h, rename=("A-", "B-"))
    assert isinstance(combined, fnx_cls)
    assert sorted(combined.nodes()) == ["A-a", "A-b", "B-c", "B-d"]


# ---------------------------------------------------------------------------
# franken_networkx-uphdr: broader 'key' attr collision — cartesian_product,
# compose, relabel_nodes, tensor_product, etc. must not TypeError when an
# edge attribute is literally named 'key'.
# ---------------------------------------------------------------------------


def _mg_with_key_attr():
    g = fnx.MultiGraph()
    g.add_edge("x", "y", weight=1)
    g["x"]["y"][0]["key"] = "sentinel"
    return g


def test_cartesian_product_preserves_edge_attribute_named_key():
    a = _mg_with_key_attr()
    b = fnx.MultiGraph(); b.add_edge("p", "q")
    product = fnx.cartesian_product(a, b)
    # Should not have raised; verify the 'key' attribute round-tripped.
    assert any(
        "key" in data and data["key"] == "sentinel"
        for _, _, _, data in product.edges(keys=True, data=True)
    )


def test_relabel_nodes_preserves_edge_attribute_named_key():
    g = _mg_with_key_attr()
    relabeled = fnx.relabel_nodes(g, {"x": "X"}, copy=True)
    assert sorted(relabeled.nodes()) == ["X", "y"]
    edges = list(relabeled.edges(keys=True, data=True))
    assert edges == [("X", "y", 0, {"weight": 1, "key": "sentinel"})]


def test_tensor_product_preserves_edge_attribute_named_key():
    a = _mg_with_key_attr()
    b = fnx.MultiGraph(); b.add_edge("p", "q")
    # tensor_product should not raise with 'key' attr present
    product = fnx.tensor_product(a, b)
    assert isinstance(product, (fnx.MultiGraph, fnx.Graph))


# ---------------------------------------------------------------------------
# franken_networkx-yr7kf: _fnx_to_nx must handle attr names that collide
# with nx's add_node / add_edge positional parameters.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("attr_name", ["node_for_adding", "u_of_edge", "v_of_edge"])
def test_fnx_to_nx_handles_collision_node_attr(attr_name):
    from franken_networkx.backend import _fnx_to_nx

    fg = fnx.Graph()
    fg.add_node("a")
    fg.nodes["a"][attr_name] = "sentinel"
    result = _fnx_to_nx(fg)
    assert dict(result.nodes["a"]) == {attr_name: "sentinel"}


@pytest.mark.parametrize("attr_name", ["node_for_adding", "u_of_edge", "v_of_edge"])
def test_fnx_to_nx_handles_collision_edge_attr(attr_name):
    """Set the attr via item-assignment (not kwargs), since nx and fnx
    both raise TypeError if you try to pass it through add_edge's
    ``**attr`` collecting-kwargs slot — the name collides with the
    positional ``u_of_edge`` / ``v_of_edge`` params."""
    from franken_networkx.backend import _fnx_to_nx

    fg = fnx.Graph()
    fg.add_edge("a", "b")
    fg["a"]["b"][attr_name] = "sentinel"
    result = _fnx_to_nx(fg)
    assert dict(result["a"]["b"]) == {attr_name: "sentinel"}


def test_fnx_to_nx_handles_collision_on_multigraph_edge_attrs():
    from franken_networkx.backend import _fnx_to_nx

    fg = fnx.MultiGraph()
    fg.add_edge("a", "b", u_of_edge="x", v_of_edge="y")
    result = _fnx_to_nx(fg)
    edges = list(result.edges(keys=True, data=True))
    assert edges == [("a", "b", 0, {"u_of_edge": "x", "v_of_edge": "y"})]


# ---------------------------------------------------------------------------
# Regression: franken_networkx-keystr — KeyError arg preserves native key
# ---------------------------------------------------------------------------


class TestKeyErrorPreservesKey:
    """The Rust view __getitem__ previously stringified the missing key in
    the raised KeyError (G[99] -> KeyError('99') str; G[(0,0)] ->
    KeyError('(0, 0)') str). Typed except-handlers that inspect
    ``e.args[0]`` got the wrong type.
    """

    def test_graph_getitem_preserves_int_key(self):
        G = fnx.path_graph(3)
        with pytest.raises(KeyError) as exc_info:
            G[99]
        assert exc_info.value.args[0] == 99
        assert isinstance(exc_info.value.args[0], int)

    def test_adj_getitem_preserves_int_key(self):
        G = fnx.path_graph(3)
        with pytest.raises(KeyError) as exc_info:
            G.adj[99]
        assert exc_info.value.args[0] == 99
        assert isinstance(exc_info.value.args[0], int)

    def test_nodes_getitem_preserves_int_key(self):
        G = fnx.path_graph(3)
        with pytest.raises(KeyError) as exc_info:
            G.nodes[99]
        assert exc_info.value.args[0] == 99
        assert isinstance(exc_info.value.args[0], int)

    def test_graph_getitem_preserves_tuple_key(self):
        G = fnx.grid_2d_graph(2, 2)
        with pytest.raises(KeyError) as exc_info:
            G[(99, 99)]
        assert exc_info.value.args[0] == (99, 99)
        assert isinstance(exc_info.value.args[0], tuple)

    def test_graph_getitem_preserves_str_key(self):
        G = fnx.Graph()
        G.add_node("a")
        with pytest.raises(KeyError) as exc_info:
            G["missing"]
        assert exc_info.value.args[0] == "missing"
        assert isinstance(exc_info.value.args[0], str)

    def test_digraph_nodes_preserves_int_key(self):
        D = fnx.DiGraph()
        D.add_edge(0, 1)
        with pytest.raises(KeyError) as exc_info:
            D.nodes[99]
        assert exc_info.value.args[0] == 99

    def test_multigraph_nodes_preserves_int_key(self):
        MG = fnx.MultiGraph()
        MG.add_edge(0, 1)
        with pytest.raises(KeyError) as exc_info:
            MG.nodes[99]
        assert exc_info.value.args[0] == 99

    def test_multidigraph_nodes_preserves_int_key(self):
        MD = fnx.MultiDiGraph()
        MD.add_edge(0, 1)
        with pytest.raises(KeyError) as exc_info:
            MD.nodes[99]
        assert exc_info.value.args[0] == 99


# ---------------------------------------------------------------------------
# Regression: franken_networkx-ndvlst — dict(G.nodes(data="attr"))
# ---------------------------------------------------------------------------


class TestNodeViewDictProtocol:
    """Before the fix, fnx.Graph.nodes(data='attr') returned the underlying
    NodeView unchanged. list() iterated (node, value) tuples correctly,
    but dict() used the view.keys()/getitem path and returned the full
    attrs dict under each node key. nx's NodeDataView has no `keys()`, so
    dict() iterates the tuples correctly.
    """

    @pytest.mark.parametrize("cls_name", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
    def test_nodes_data_attr_dict_coerce_matches_networkx(self, cls_name):
        import networkx as nx

        G = getattr(fnx, cls_name)()
        G.add_edge(0, 1)
        G.add_edge(1, 2)
        G.nodes[0]["color"] = "red"
        G.nodes[1]["color"] = "blue"

        Gn = getattr(nx, cls_name)()
        Gn.add_edge(0, 1)
        Gn.add_edge(1, 2)
        Gn.nodes[0]["color"] = "red"
        Gn.nodes[1]["color"] = "blue"

        assert dict(G.nodes(data="color")) == dict(Gn.nodes(data="color"))

    def test_nodes_data_attr_default_honoured(self):
        G = fnx.path_graph(3)
        G.nodes[0]["tag"] = "a"
        assert dict(G.nodes(data="tag", default="zz")) == {0: "a", 1: "zz", 2: "zz"}

    def test_convert_node_labels_to_integers_label_attribute(self):
        """convert_node_labels_to_integers(G, label_attribute='old') uses
        dict(G.nodes(data='old')) internally (indirectly via nx's
        attribute-coalescing code path). This exercises the ndvlst bug
        through a common nx utility.
        """
        r = fnx.convert_node_labels_to_integers(
            fnx.path_graph(3), label_attribute="old"
        )
        assert dict(r.nodes(data="old")) == {0: 0, 1: 1, 2: 2}


# ---------------------------------------------------------------------------
# Regression: franken_networkx-evdvlst — EdgeView(data=...) materializes list
# ---------------------------------------------------------------------------


class TestEdgeViewDataProtocol:
    """Before the fix, G.edges(data='attr') retained the raw EdgeView with
    keys() / __getitem__ attached. dict() then used the keys path and
    produced a garbage {(u, v, val): {attr: val}} mapping. nx's
    EdgeDataView has no keys(), so dict() raises ValueError. Matching nx
    (either both error or both yield identical content) is what parity
    requires.
    """

    @pytest.mark.parametrize("cls_name", ["Graph", "DiGraph"])
    def test_edges_data_str_dict_coerce_matches_networkx_error(self, cls_name):
        import networkx as nx

        G = getattr(fnx, cls_name)()
        G.add_edge(0, 1, w=1.5)
        G.add_edge(1, 2, w=2.5)
        Gn = getattr(nx, cls_name)()
        Gn.add_edge(0, 1, w=1.5)
        Gn.add_edge(1, 2, w=2.5)

        # dict(edge_view(data='w')) must either raise ValueError on both
        # sides or yield the same mapping on both sides. Matching the
        # error behavior is the drop-in contract.
        fnx_err = None
        nx_err = None
        try:
            dict(G.edges(data="w"))
        except Exception as e:
            fnx_err = type(e).__name__
        try:
            dict(Gn.edges(data="w"))
        except Exception as e:
            nx_err = type(e).__name__
        assert fnx_err == nx_err, f"fnx raised {fnx_err}, nx raised {nx_err}"

    def test_edges_data_str_list_iter_matches(self):
        import networkx as nx

        G = fnx.Graph()
        G.add_edge(0, 1, w=1.5)
        G.add_edge(1, 2, w=2.5)
        Gn = nx.Graph()
        Gn.add_edge(0, 1, w=1.5)
        Gn.add_edge(1, 2, w=2.5)
        assert list(G.edges(data="w")) == list(Gn.edges(data="w"))

    def test_edges_data_true_list_iter_matches(self):
        import networkx as nx

        G = fnx.Graph()
        G.add_edge(0, 1, w=1.5)
        Gn = nx.Graph()
        Gn.add_edge(0, 1, w=1.5)
        assert list(G.edges(data=True)) == list(Gn.edges(data=True))


# ---------------------------------------------------------------------------
# Regression: franken_networkx-privadj — private _adj/_node/_succ/_pred aliases
# ---------------------------------------------------------------------------


class TestPrivateAdjAliases:
    """Many nx internals reach into G._adj / G._node / G._succ / G._pred
    (e.g. nx.algorithms.bipartite.is_bipartite_node_set does
    connected_components(G) which accesses G._adj directly). fnx graphs
    must expose these private aliases so nx's internal read paths work
    when fnx graphs are passed into nx helper routines.
    """

    def test_graph_has_private_adj_alias(self):
        G = fnx.path_graph(3)
        assert hasattr(G, "_adj")
        assert list(G._adj[0]) == [1]

    def test_graph_has_private_node_alias(self):
        G = fnx.path_graph(3)
        G.nodes[0]["color"] = "red"
        assert hasattr(G, "_node")
        assert G._node[0]["color"] == "red"

    def test_digraph_has_succ_pred_aliases(self):
        D = fnx.DiGraph()
        D.add_edge(0, 1)
        D.add_edge(1, 2)
        assert list(D._succ[0]) == [1]
        assert list(D._pred[2]) == [1]

    def test_multidigraph_has_succ_pred_aliases(self):
        MD = fnx.MultiDiGraph()
        MD.add_edge(0, 1)
        MD.add_edge(1, 2)
        assert list(MD._succ[0]) == [1]
        assert list(MD._pred[2]) == [1]

    def test_nx_bipartite_works_on_fnx_graph(self):
        """End-to-end: call an nx helper that reaches into G._adj on an
        fnx graph. Previously crashed with AttributeError: 'franken_networkx.Graph'
        object has no attribute '_adj'.
        """
        from networkx.algorithms import bipartite as nxb

        G = fnx.complete_bipartite_graph(3, 4)
        assert nxb.is_bipartite_node_set(G, [0, 1, 2]) is True

    def test_nx_connected_components_on_fnx_graph(self):
        """nx's connected_components reaches G._adj via _plain_bfs."""
        import networkx as nx

        G = fnx.Graph([(0, 1), (1, 2), (3, 4)])
        comps = sorted(sorted(c) for c in nx.connected_components(G))
        assert comps == [[0, 1, 2], [3, 4]]


# ---------------------------------------------------------------------------
# Regression: franken_networkx-dcpy — deepcopy isolates nested attr values
# ---------------------------------------------------------------------------


class TestDeepCopyIsolation:
    """The Rust __deepcopy__ built-in did not deep-copy nested values
    inside node/edge/graph attrs. Mutating a list inside
    H.nodes[n]['x'] also mutated G.nodes[n]['x']. Python-level override
    re-constructs the graph with deepcopy() on every attrs dict.
    """

    @pytest.mark.parametrize("cls_name", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
    def test_node_attr_nested_list_isolation(self, cls_name):
        import copy

        G = getattr(fnx, cls_name)()
        G.add_edge(0, 1)
        G.nodes[0]["x"] = [1, 2, 3]
        H = copy.deepcopy(G)
        H.nodes[0]["x"].append(99)
        assert G.nodes[0]["x"] == [1, 2, 3]
        assert H.nodes[0]["x"] == [1, 2, 3, 99]

    @pytest.mark.parametrize("cls_name", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
    def test_graph_level_attr_isolation(self, cls_name):
        import copy

        G = getattr(fnx, cls_name)()
        G.graph["names"] = ["a", "b"]
        H = copy.deepcopy(G)
        H.graph["names"].append("c")
        assert G.graph["names"] == ["a", "b"]
        assert H.graph["names"] == ["a", "b", "c"]

    def test_multigraph_edge_attr_isolation(self):
        import copy

        MG = fnx.MultiGraph()
        MG.add_edge(0, 1, key="a", data=[1, 2])
        MG.add_edge(0, 1, key="b", data=[3, 4])
        MH = copy.deepcopy(MG)
        MH[0][1]["a"]["data"].append(99)
        assert MG[0][1]["a"]["data"] == [1, 2]
        assert MH[0][1]["a"]["data"] == [1, 2, 99]


# ---------------------------------------------------------------------------
# Regression: br-r37-c1-3tlkj — G.copy() must be SHALLOW (matches nx)
# ---------------------------------------------------------------------------


class TestGraphCopyIsShallow:
    """nx.Graph.copy() docstring: 'an independent shallow copy of the
    graph and attributes. That is, if an attribute is a container,
    that container is shared by the original and the copy.' Pre-fix
    fnx.G.copy() did a deep copy, which produced independent inner
    containers — code that intentionally relied on shared mutation
    of nested attrs (e.g. caching layers) silently broke. This test
    cross-checks identity against nx so any future regression is
    caught immediately.

    Note: copy.deepcopy(G) — the Python builtin — must STILL deep-copy.
    See TestDeepCopyIsolation above for that contract.
    """

    @pytest.mark.parametrize("cls_name", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
    def test_node_attr_inner_container_is_shared(self, cls_name):
        import networkx as nx

        G = getattr(fnx, cls_name)()
        Gn = getattr(nx, cls_name)()
        G.add_node(1, payload={"list": [1, 2, 3]})
        Gn.add_node(1, payload={"list": [1, 2, 3]})

        H = G.copy()
        Hn = Gn.copy()

        assert (H.nodes[1]["payload"] is G.nodes[1]["payload"]) == (
            Hn.nodes[1]["payload"] is Gn.nodes[1]["payload"]
        ), "node-attr container identity must match nx"
        # And nx's contract is sharing — so both sides are True.
        assert H.nodes[1]["payload"] is G.nodes[1]["payload"]

    @pytest.mark.parametrize("cls_name", ["Graph", "DiGraph"])
    def test_edge_attr_inner_container_is_shared(self, cls_name):
        import networkx as nx

        G = getattr(fnx, cls_name)()
        Gn = getattr(nx, cls_name)()
        G.add_edge(2, 3, payload={"list": [4, 5]})
        Gn.add_edge(2, 3, payload={"list": [4, 5]})

        H = G.copy()
        Hn = Gn.copy()

        assert (H[2][3]["payload"] is G[2][3]["payload"]) == (
            Hn[2][3]["payload"] is Gn[2][3]["payload"]
        )
        assert H[2][3]["payload"] is G[2][3]["payload"]

    def test_multigraph_edge_attr_inner_container_is_shared(self):
        import networkx as nx

        G = fnx.MultiGraph()
        Gn = nx.MultiGraph()
        G.add_edge(2, 3, key="a", payload={"list": [4, 5]})
        Gn.add_edge(2, 3, key="a", payload={"list": [4, 5]})

        H = G.copy()
        Hn = Gn.copy()

        assert (H[2][3]["a"]["payload"] is G[2][3]["a"]["payload"]) == (
            Hn[2][3]["a"]["payload"] is Gn[2][3]["a"]["payload"]
        )
        assert H[2][3]["a"]["payload"] is G[2][3]["a"]["payload"]

    @pytest.mark.parametrize("cls_name", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
    def test_graph_attr_inner_container_is_shared(self, cls_name):
        import networkx as nx

        G = getattr(fnx, cls_name)()
        Gn = getattr(nx, cls_name)()
        G.graph["names"] = ["a", "b"]
        Gn.graph["names"] = ["a", "b"]

        H = G.copy()
        Hn = Gn.copy()

        assert (H.graph["names"] is G.graph["names"]) == (
            Hn.graph["names"] is Gn.graph["names"]
        )
        assert H.graph["names"] is G.graph["names"]

    @pytest.mark.parametrize("cls_name", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
    def test_top_level_attr_dict_is_independent(self, cls_name):
        """The OUTER attrs dict is a fresh copy — adding a new key
        on H.nodes[n] must not appear on G.nodes[n]. Verifies the
        copy isn't a view."""
        G = getattr(fnx, cls_name)()
        G.add_node(1, color="red")

        H = G.copy()
        H.nodes[1]["new_key"] = "added"

        assert "new_key" not in G.nodes[1]
        assert H.nodes[1]["new_key"] == "added"

    @pytest.mark.parametrize("cls_name", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
    def test_inner_container_mutation_visible_to_original(self, cls_name):
        """The behavioral expression of the shallow-copy contract:
        appending to the inner list of a copied node attr propagates
        to the original. This is what existing nx user code relies
        on."""
        import networkx as nx

        G = getattr(fnx, cls_name)()
        Gn = getattr(nx, cls_name)()
        G.add_node(1, payload=[1, 2])
        Gn.add_node(1, payload=[1, 2])

        G.copy().nodes[1]["payload"].append(99)
        Gn.copy().nodes[1]["payload"].append(99)

        assert G.nodes[1]["payload"] == Gn.nodes[1]["payload"] == [1, 2, 99]


# ---------------------------------------------------------------------------
# Regression: franken_networkx-degnbn — G.degree(nbunch) skips missing nodes
# ---------------------------------------------------------------------------


class TestDegreeNbunchFilter:
    """G.degree(nbunch) with missing nodes in nbunch must silently skip
    them per nx contract (nbunch_iter semantics). fnx previously raised
    NodeNotFound on the first missing node.
    """

    def test_graph_degree_skips_missing_nodes(self):
        import networkx as nx

        G = fnx.path_graph(3)
        Gn = nx.path_graph(3)
        assert list(G.degree([0, 1, 99])) == list(Gn.degree([0, 1, 99]))

    def test_graph_degree_all_missing_yields_empty(self):
        G = fnx.path_graph(3)
        assert list(G.degree([99, 100])) == []

    def test_digraph_in_degree_skips_missing(self):
        import networkx as nx

        D = fnx.DiGraph([(0, 1), (1, 2)])
        Dn = nx.DiGraph([(0, 1), (1, 2)])
        assert list(D.in_degree([0, 1, 99])) == list(Dn.in_degree([0, 1, 99]))

    def test_digraph_out_degree_skips_missing(self):
        import networkx as nx

        D = fnx.DiGraph([(0, 1), (1, 2)])
        Dn = nx.DiGraph([(0, 1), (1, 2)])
        assert list(D.out_degree([0, 1, 99])) == list(Dn.out_degree([0, 1, 99]))

    def test_degree_single_node_still_raises_on_missing(self):
        """Single-node lookup (non-iterable) should still error — only
        iterable nbunches get the skip treatment.
        """
        G = fnx.path_graph(3)
        with pytest.raises((fnx.NodeNotFound, KeyError)):
            G.degree(99)


# ---------------------------------------------------------------------------
# Regression: franken_networkx-edgekey — EdgeView.__getitem__ preserves key type
# ---------------------------------------------------------------------------


class TestEdgeViewKeyErrorPreserved:
    """G.edges[u, v] / G.edges[u, v, k] on a missing edge previously
    raised KeyError with a stringified repr of the tuple. The Python
    override preserves the original tuple.
    """

    def test_graph_edges_missing_preserves_tuple(self):
        G = fnx.path_graph(3)
        with pytest.raises(KeyError) as exc_info:
            G.edges[5, 6]
        assert exc_info.value.args[0] == (5, 6)
        assert isinstance(exc_info.value.args[0], tuple)

    def test_digraph_edges_missing_preserves_tuple(self):
        D = fnx.DiGraph([(0, 1)])
        with pytest.raises(KeyError) as exc_info:
            D.edges[5, 6]
        assert exc_info.value.args[0] == (5, 6)

    def test_multigraph_edges_missing_triple_preserves_tuple(self):
        MG = fnx.MultiGraph([(0, 1)])
        with pytest.raises(KeyError) as exc_info:
            MG.edges[0, 1, "missing"]
        assert exc_info.value.args[0] == (0, 1, "missing")


# ---------------------------------------------------------------------------
# Regression: franken_networkx-vweqset — EdgeView Set.__eq__ semantics
# ---------------------------------------------------------------------------


class TestEdgeViewSetEquality:
    """nx.EdgeView inherits from collections.abc.Set so
    `G.edges == {(0,1), (1,2)}` returns True. fnx's EdgeView was a bare
    Rust type with no ABC inheritance, so the same comparison returned
    False. NodeView is intentionally left as Mapping-semantics (returns
    False on set equality, matching nx's Mapping-first __eq__).
    """

    def test_edges_equal_set(self):
        import networkx as nx

        G = fnx.path_graph(3)
        Gn = nx.path_graph(3)
        assert (G.edges == {(0, 1), (1, 2)}) == (Gn.edges == {(0, 1), (1, 2)})
        assert G.edges == {(0, 1), (1, 2)}

    def test_edges_not_equal_different_set(self):
        G = fnx.path_graph(3)
        assert G.edges != {(0, 1)}
        assert G.edges != {(5, 6)}

    def test_edges_isdisjoint(self):
        G = fnx.path_graph(3)
        assert G.edges.isdisjoint({(5, 6)})
        assert not G.edges.isdisjoint({(0, 1), (5, 6)})

    def test_nodes_not_equal_plain_set_mirrors_nx_mapping(self):
        """NodeView is a Mapping in nx, not a Set, so it does NOT compare
        equal to a plain node set. The wrapper must preserve that
        contract.
        """
        import networkx as nx

        G = fnx.path_graph(3)
        Gn = nx.path_graph(3)
        assert (G.nodes == {0, 1, 2}) is False
        assert (Gn.nodes == {0, 1, 2}) is False
        # But set(nodes) does equal the set.
        assert set(G.nodes) == {0, 1, 2}

    def test_edges_unhashable(self):
        """Once __eq__ is defined, __hash__ must be None (Python protocol)."""
        G = fnx.path_graph(3)
        with pytest.raises(TypeError):
            hash(G.edges)


# ---------------------------------------------------------------------------
# Regression: franken_networkx-nvupdt — G._node supports dict-style update
# ---------------------------------------------------------------------------


class TestPrivateNodeFacadeUpdate:
    """nx internals (relabel._relabel_copy) do
    ``H._node.update((node, attrs) for ...)``. fnx's _node alias used
    to return the read-only NodeView, which crashed that path with
    AttributeError. The _PrivateNodeFacade wrapper exposes dict-style
    read + bulk write semantics.
    """

    def test_nx_convert_node_labels_works_on_fnx(self):
        import networkx as nx

        r = nx.convert_node_labels_to_integers(fnx.path_graph(3))
        assert sorted(r.nodes) == [0, 1, 2]
        assert sorted(r.edges) == [(0, 1), (1, 2)]

    def test_nx_relabel_nodes_works_on_fnx(self):
        import networkx as nx

        r = nx.relabel_nodes(fnx.path_graph(3), {0: "a", 1: "b", 2: "c"})
        assert sorted(r.nodes, key=str) == ["a", "b", "c"]

    def test_private_node_facade_update_iterable(self):
        G = fnx.Graph()
        G._node.update(((n, {"tag": n}) for n in range(3)))
        assert sorted(G.nodes) == [0, 1, 2]
        assert G.nodes[0] == {"tag": 0}
        assert G.nodes[2] == {"tag": 2}

    def test_private_node_facade_supports_setitem(self):
        G = fnx.Graph()
        G.add_node(0)
        G._node[0] = {"color": "red"}
        assert G.nodes[0] == {"color": "red"}

    def test_private_node_facade_items_roundtrip(self):
        G = fnx.path_graph(3)
        G.nodes[1]["x"] = 1
        items = list(G._node.items())
        assert len(items) == 3
        assert dict(items[1][1]) == {"x": 1}


# ---------------------------------------------------------------------------
# Regression: franken_networkx-edgesnb — EdgeView accepts single-node nbunch
# ---------------------------------------------------------------------------


class TestEdgeViewSingleNodeNbunch:
    """nx.EdgeView accepts a single node as nbunch, yielding edges
    incident to that node. The Rust edge_view_call expected only
    None or an iterable; a single node raised
    TypeError: 'int' object is not iterable. That in turn broke
    nx.line_graph() on fnx because its internal helper called
    `G.edges(u)` with a single node u.
    """

    def test_edges_single_int_nbunch(self):
        import networkx as nx

        G = fnx.path_graph(4)
        G.add_edge(0, 2)
        assert set(G.edges(0)) == {(0, 1), (0, 2)}

    def test_edges_single_str_nbunch(self):
        G = fnx.Graph([("a", "b"), ("b", "c")])
        assert set(G.edges("a")) == {("a", "b")}

    def test_nx_line_graph_works_on_fnx(self):
        import networkx as nx

        G = fnx.path_graph(4)
        G.add_edge(0, 2)
        L = nx.line_graph(G)
        assert sorted(L.nodes) == [(0, 1), (0, 2), (1, 2), (2, 3)]

    def test_edges_iterable_nbunch_still_works(self):
        G = fnx.path_graph(4)
        # List + set nbunches remain iterable
        assert sorted(tuple(sorted(e)) for e in G.edges([0, 1])) == [(0, 1), (1, 2)]
        assert sorted(tuple(sorted(e)) for e in G.edges({1, 2})) == [(0, 1), (1, 2), (2, 3)]


# ---------------------------------------------------------------------------
# Regression: franken_networkx-edgesu1 — G.edges(u) yields (u, v) first
# ---------------------------------------------------------------------------


class TestEdgeViewNbunchOrdering:
    """nx's `G.edges(u)` yields tuples with the queried node first:
    `G.edges(3) -> [(3, 2)]`. fnx's EdgeView canonicalized to (min, max),
    breaking nx internals like degree_assortativity_coefficient that do
    `for _, nbr in G.edges(u)` assuming the first element is u.
    """

    def test_edges_single_queried_node_first(self):
        import networkx as nx

        G = fnx.path_graph(4)
        G.add_edge(0, 2)
        Gn = nx.path_graph(4)
        Gn.add_edge(0, 2)
        assert list(G.edges(3)) == list(Gn.edges(3))

    def test_edges_list_nbunch_preserves_incident_ordering(self):
        import networkx as nx

        G = fnx.path_graph(4)
        G.add_edge(0, 2)
        Gn = nx.path_graph(4)
        Gn.add_edge(0, 2)
        # Each emitted edge should have a nbunch node first.
        for e in G.edges([0, 3]):
            assert e[0] in {0, 3}

    def test_nx_degree_assortativity_on_fnx_matches_nx(self):
        """br-edgesu1: nx.degree_assortativity_coefficient reads
        `G.edges(u)` and assumes tuples are (u, nbr); fnx canonicalization
        previously produced wrong correlation values.
        """
        import networkx as nx

        G = fnx.path_graph(4)
        G.add_edge(0, 2)
        Gn = nx.path_graph(4)
        Gn.add_edge(0, 2)
        assert abs(
            nx.degree_assortativity_coefficient(G)
            - nx.degree_assortativity_coefficient(Gn)
        ) < 1e-9


# ---------------------------------------------------------------------------
# Regression: franken_networkx-edgesnone — G.edges(data=None, default=X)
# ---------------------------------------------------------------------------


class TestEdgeViewDataNone:
    """nx.Graph.edges(data=None, default=X) yields 3-tuples with the
    default as the third element for every edge. The Rust EdgeView
    treated data=None the same as data=False (2-tuples), breaking nx
    internals like eigenvector_centrality_numpy / katz_centrality_numpy /
    resistance_distance that internally call edges(data=weight, default=1)
    with weight=None.
    """

    def test_edges_data_none_yields_default(self):
        import networkx as nx

        G = fnx.path_graph(4)
        G.add_edge(0, 2)
        Gn = nx.path_graph(4)
        Gn.add_edge(0, 2)
        assert list(G.edges(data=None, default=1)) == list(
            Gn.edges(data=None, default=1)
        )

    def test_nx_eigenvector_centrality_numpy_on_fnx(self):
        import networkx as nx

        G = fnx.path_graph(4)
        G.add_edge(0, 2)
        r = nx.eigenvector_centrality_numpy(G)
        Gn = nx.path_graph(4)
        Gn.add_edge(0, 2)
        rn = nx.eigenvector_centrality_numpy(Gn)
        for k in r:
            assert abs(r[k] - rn[k]) < 1e-6

    def test_nx_resistance_distance_on_fnx(self):
        import networkx as nx

        G = fnx.path_graph(4)
        G.add_edge(0, 2)
        Gn = nx.path_graph(4)
        Gn.add_edge(0, 2)
        assert abs(nx.resistance_distance(G, 0, 3) - nx.resistance_distance(Gn, 0, 3)) < 1e-9

    def test_edges_data_false_still_yields_2tuples(self):
        G = fnx.path_graph(3)
        edges = list(G.edges(data=False))
        assert all(len(e) == 2 for e in edges)


# ---------------------------------------------------------------------------
# Regression: franken_networkx-addedgesgen — add_edges_from(gen reading self)
# ---------------------------------------------------------------------------


class TestAddEdgesFromReadsSelf:
    """nx internals frequently call
    ``G.add_edges_from(gen_that_reads_G)`` (e.g. transitive_closure does
    ``TC.add_edges_from((v, e[1]) for e in ... if e[1] not in TC[v])``).
    The Rust add_edges_from mutably borrows self while iterating the
    ebunch, and the generator's read of ``TC[v]`` then tries to acquire
    an immutable borrow on the same RefCell, raising
    ``RuntimeError: Already mutably borrowed``. Python wrapper
    materializes the ebunch into a list first.
    """

    def test_add_edges_from_generator_reading_self(self):
        G = fnx.DiGraph()
        G.add_node(0)
        G.add_node(1)
        G.add_node(2)
        gen = ((0, v) for v in [1, 2] if v not in G[0])
        G.add_edges_from(gen)  # must not raise
        assert sorted(G.edges) == [(0, 1), (0, 2)]

    def test_nx_transitive_closure_works_on_fnx(self):
        import networkx as nx

        D = fnx.DiGraph([(0, 1), (1, 2), (2, 0), (0, 3)])
        r = nx.transitive_closure(D)
        assert r.number_of_edges() == 12
        assert sorted(r.edges) == sorted(
            nx.transitive_closure(nx.DiGraph([(0, 1), (1, 2), (2, 0), (0, 3)])).edges
        )

    def test_graph_add_edges_from_with_self_reading_gen(self):
        """Same pattern on simple Graph."""
        G = fnx.Graph([(0, 1), (1, 2), (2, 3)])
        # Read G.adj (safe dict access) while add_edges_from is mutating.
        gen = ((u, v) for u, v in [(0, 3), (2, 0)] if v not in G.adj.get(u, {}))
        G.add_edges_from(gen)  # must not raise due to borrow conflict
        assert G.has_edge(0, 3)
        assert G.has_edge(2, 0)


# ---------------------------------------------------------------------------
# Regression: franken_networkx-adjkset — AdjacencyView.keys() supports set ops
# ---------------------------------------------------------------------------


class TestAdjacencyViewKeysSetOps:
    """nx.non_neighbors does ``graph._adj.keys() - graph._adj[node].keys() - {node}``
    expecting dict_keys-like views that support set-difference. fnx's
    AdjacencyView.keys() was a plain iterator, so the subtraction raised
    TypeError. AtlasView inner keys() has the same issue. Fix: keys()
    returns a KeysView subclass with full set-operation support.
    """

    def test_adj_keys_supports_set_difference(self):
        G = fnx.complete_graph(5)
        diff = G.adj.keys() - {1, 2}
        assert diff == {0, 3, 4}

    def test_adj_inner_keys_supports_intersection(self):
        G = fnx.complete_graph(5)
        common = G.adj[0].keys() & G.adj[1].keys()
        assert common == {2, 3, 4}

    def test_nx_non_neighbors_works_on_fnx(self):
        import networkx as nx

        G = fnx.path_graph(5)  # 0-1-2-3-4
        assert sorted(nx.non_neighbors(G, 0)) == [2, 3, 4]

    def test_nx_approximation_clique_removal_works_on_fnx(self):
        import networkx as nx

        G = fnx.complete_graph(5)
        iset, cliques = nx.approximation.clique_removal(G)
        assert len(cliques) == 1
        assert {0, 1, 2, 3, 4} == cliques[0]


# ---------------------------------------------------------------------------
# Regression: franken_networkx-grattrset — G.graph = {...} assignment
# ---------------------------------------------------------------------------


class TestGraphAttrsAssignable:
    """nx internals (subgraph_view, restricted_view, and any code that
    builds a new graph and then does ``newG.graph = G.graph``) need
    ``G.graph`` to be assignable. The Rust-native .graph is a
    read-only getset_descriptor so the assignment raised
    ``AttributeError: attribute 'graph' of 'franken_networkx.Graph'
    objects is not writable``. The _GraphAttrsDescriptor wrapper
    adds a __set__ that clears + updates the underlying dict in place.
    """

    def test_graph_attr_assignment_replaces_contents(self):
        G = fnx.Graph()
        G.graph["old_key"] = "old_value"
        G.graph = {"name": "test", "tag": "x"}
        assert dict(G.graph) == {"name": "test", "tag": "x"}

    def test_graph_attr_assignment_preserves_identity(self):
        """In-place clear+update: the same dict object is reused so
        references held elsewhere (e.g. nx.subgraph_view newG.graph = G.graph)
        continue to see the updated contents.
        """
        G = fnx.Graph()
        before = G.graph
        G.graph = {"foo": "bar"}
        after = G.graph
        assert before is after
        assert dict(after) == {"foo": "bar"}

    def test_graph_attr_delete_clears(self):
        G = fnx.Graph(name="keep")
        assert dict(G.graph) == {"name": "keep"}
        del G.graph
        assert dict(G.graph) == {}

    def test_all_four_classes_support_graph_assign(self):
        for cls in (fnx.Graph, fnx.DiGraph, fnx.MultiGraph, fnx.MultiDiGraph):
            G = cls()
            G.graph = {"role": "test"}
            assert dict(G.graph) == {"role": "test"}


# ---------------------------------------------------------------------------
# Regression: franken_networkx-adjcp — AdjacencyView.copy for MultiGraph
# ---------------------------------------------------------------------------


class TestAdjacencyViewCopy:
    """Earlier br-atlascp added copy() to AtlasView. MultiGraph's inner
    adjacency is an AdjacencyView (G.adj[u] -> dict-of-keyed-attrs); it
    also lacked copy(), so nx.to_dict_of_dicts(fnx_multigraph) crashed
    with 'AdjacencyView object has no attribute copy'.
    """

    def test_adj_view_copy_on_multigraph(self):
        import networkx as nx

        MG = fnx.MultiGraph()
        MG.add_edge(0, 1, key="a", w=1)
        MG.add_edge(0, 1, key="b", w=2)
        MG.add_edge(1, 2, key=0, w=3)
        MGn = nx.MultiGraph()
        MGn.add_edge(0, 1, key="a", w=1)
        MGn.add_edge(0, 1, key="b", w=2)
        MGn.add_edge(1, 2, key=0, w=3)
        assert nx.to_dict_of_dicts(MG) == nx.to_dict_of_dicts(MGn)

    def test_adj_view_copy_directly(self):
        MG = fnx.MultiGraph()
        MG.add_edge(0, 1, key="a")
        MG.add_edge(0, 1, key="b")
        assert MG.adj[0].copy() == {1: {"a": {}, "b": {}}}

    def test_multi_adj_view_copy_deep(self):
        """MultiAdjacencyView.copy() should snapshot the full
        dict-of-dicts-of-dicts structure.
        """
        MG = fnx.MultiGraph()
        MG.add_edge(0, 1, key=0, w=5)
        snapshot = MG.adj.copy()
        assert snapshot == {0: {1: {0: {"w": 5}}}, 1: {0: {0: {"w": 5}}}}


# ---------------------------------------------------------------------------
# Regression: franken_networkx-classpred — is_directed/is_multigraph on class
# ---------------------------------------------------------------------------


class TestClassLevelPredicates:
    """nx.utils.misc.check_create_using does
    ``G.is_directed(None) if isinstance(G, type) else G.is_directed()``
    when deciding whether a create_using CLASS matches expected
    directedness. On nx, these are plain methods that ignore self, so
    passing self=None works. fnx's Rust descriptors required a real
    instance and raised TypeError. Wrapper makes is_directed /
    is_multigraph callable on the class (returning the class-level
    default) without breaking instance-level calls.
    """

    def test_class_level_is_directed(self):
        assert fnx.Graph.is_directed(None) is False
        assert fnx.DiGraph.is_directed(None) is True
        assert fnx.MultiGraph.is_directed(None) is False
        assert fnx.MultiDiGraph.is_directed(None) is True

    def test_class_level_is_multigraph(self):
        assert fnx.Graph.is_multigraph(None) is False
        assert fnx.DiGraph.is_multigraph(None) is False
        assert fnx.MultiGraph.is_multigraph(None) is True
        assert fnx.MultiDiGraph.is_multigraph(None) is True

    def test_instance_level_still_works(self):
        G = fnx.Graph()
        D = fnx.DiGraph()
        MG = fnx.MultiGraph()
        MD = fnx.MultiDiGraph()
        assert G.is_directed() is False
        assert D.is_directed() is True
        assert MG.is_multigraph() is True
        assert MD.is_multigraph() is True

    def test_nx_gnp_random_graph_with_fnx_create_using(self):
        import networkx as nx

        g = nx.gnp_random_graph(10, 0.3, seed=42, create_using=fnx.Graph)
        assert isinstance(g, fnx.Graph)
        assert g.number_of_nodes() == 10

    def test_nx_barabasi_albert_with_fnx_create_using(self):
        import networkx as nx

        g = nx.barabasi_albert_graph(10, 2, seed=42, create_using=fnx.Graph)
        assert isinstance(g, fnx.Graph)
        assert g.number_of_nodes() == 10

    def test_nx_directed_gnp_with_fnx_digraph(self):
        import networkx as nx

        g = nx.gnp_random_graph(10, 0.3, seed=42, directed=True, create_using=fnx.DiGraph)
        assert isinstance(g, fnx.DiGraph)


# ---------------------------------------------------------------------------
# Regression: franken_networkx-rmvbunch — remove_*_from materialize ebunch
# ---------------------------------------------------------------------------


class TestRemoveBunchMaterialized:
    """nx internals call ``g.remove_edges_from(nx.selfloop_edges(g))`` and
    similar patterns where the iterable reads self. The Rust
    remove_edges_from / remove_nodes_from mutably borrows self while
    iterating the bunch; the generator's read raises
    ``RuntimeError: Already mutably borrowed``. Same class as
    br-addedgesgen — materialize before the Rust call.
    """

    def test_remove_edges_from_generator_reading_self(self):
        import networkx as nx

        G = fnx.Graph([(0, 1), (1, 2), (2, 0), (3, 3)])
        G.remove_edges_from(nx.selfloop_edges(G))
        assert sorted(G.edges) == [(0, 1), (0, 2), (1, 2)]

    def test_remove_nodes_from_generator_reading_self(self):
        G = fnx.path_graph(5)
        G.remove_nodes_from(n for n in [1, 2] if n in G)
        assert sorted(G.nodes) == [0, 3, 4]

    def test_nx_girvan_newman_works_on_fnx(self):
        """End-to-end: nx.community.girvan_newman calls
        g.remove_edges_from(nx.selfloop_edges(g)) internally.
        """
        import networkx as nx

        G = fnx.path_graph(5)
        G.add_edge(0, 3)
        first_split = next(nx.community.girvan_newman(G))
        assert len(first_split) == 2  # partition into 2 communities
