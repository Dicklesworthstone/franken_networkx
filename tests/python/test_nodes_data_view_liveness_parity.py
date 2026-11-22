"""Parity for ``G.nodes(data=...)`` live-view semantics and class name.

Bead br-r37-c1-j2vof. fnx ``Graph.nodes(data=True)`` returned the rust
``NodeView`` class (not ``NodeDataView`` like nx). The ``data='attr'``
path returned a Python ``list`` (also not ``NodeDataView``). Drop-in
code doing ``isinstance(view, nx.classes.reportviews.NodeDataView)``
fails. The list path additionally broke live-view semantics —
mutations after capture were not reflected.

Same root cause and fix as ``br-r37-c1-sf1ku`` (EdgeDataView): wrap
the call result in a ``NodeDataView`` class that re-invokes the
underlying call on each access.
"""

from __future__ import annotations

import copy

import pytest

import franken_networkx as fnx

try:
    import networkx as nx
    HAS_NX = True
except ImportError:
    HAS_NX = False

needs_nx = pytest.mark.skipif(not HAS_NX, reason="networkx not installed")


@needs_nx
def test_nodes_no_args_returns_node_view():
    """Plain G.nodes() should still return the live Rust NodeView —
    only data variants were buggy."""
    G = fnx.path_graph(3)
    assert type(G.nodes()).__name__ == "NodeView"


@needs_nx
def test_nodes_data_true_returns_node_data_view():
    G = fnx.path_graph(3)
    view = G.nodes(data=True)
    assert type(view).__name__ == "NodeDataView"


@needs_nx
def test_nodes_data_attr_returns_node_data_view():
    G = fnx.Graph()
    G.add_node(0, color="red")
    view = G.nodes(data="color")
    assert type(view).__name__ == "NodeDataView"


@needs_nx
def test_nodes_data_view_is_live_after_mutation():
    G = fnx.path_graph(3)
    GX = nx.path_graph(3)
    fview = G.nodes(data=True)
    nview = GX.nodes(data=True)

    G.add_node(99, x=42)
    GX.add_node(99, x=42)

    f = list(fview)
    n = list(nview)
    assert f == n
    assert (99, {"x": 42}) in f


@needs_nx
def test_nodes_data_str_view_is_live():
    G = fnx.Graph()
    G.add_node(0, color="red")
    view = G.nodes(data="color")
    initial = list(view)
    G.add_node(1, color="blue")
    after = list(view)
    assert len(after) > len(initial)
    assert (1, "blue") in after


@needs_nx
def test_nodes_data_view_len_is_live():
    G = fnx.path_graph(3)
    view = G.nodes(data=True)
    assert len(view) == 3
    G.add_node(99)
    assert len(view) == 4


@needs_nx
def test_nodes_data_str_default():
    G = fnx.Graph()
    G.add_node(0, color="red")
    G.add_node(1)
    GX = nx.Graph()
    GX.add_node(0, color="red")
    GX.add_node(1)
    f = list(G.nodes(data="color", default="UNK"))
    n = list(GX.nodes(data="color", default="UNK"))
    assert f == n


@needs_nx
def test_nodes_data_view_values_match_networkx():
    G = fnx.Graph()
    G.add_nodes_from([(0, {"x": 1}), (1, {"x": 2}), (2, {})])
    GX = nx.Graph()
    GX.add_nodes_from([(0, {"x": 1}), (1, {"x": 2}), (2, {})])
    f = list(G.nodes(data=True))
    n = list(GX.nodes(data=True))
    assert f == n


@needs_nx
def test_nodes_data_view_contains_bare_node():
    """nx NodeDataView returns True for `node in view` even when data
    is set — it strips the data and checks the underlying NodeView."""
    G = fnx.path_graph(3)
    view = G.nodes(data=True)
    assert 0 in view
    assert 99 not in view


@needs_nx
def test_nodes_data_view_repr():
    G = fnx.path_graph(2)
    view = G.nodes(data=True)
    r = repr(view)
    assert r.startswith("NodeDataView(")


@needs_nx
def test_nodes_data_view_eq_to_list():
    G = fnx.path_graph(2)
    view = G.nodes(data=True)
    assert view == [(0, {}), (1, {})]


@needs_nx
def test_nodes_data_str_attr_view_repeatable_iteration():
    """Iterating the view twice should yield the same data — the view
    must not be a one-shot generator."""
    G = fnx.Graph()
    G.add_nodes_from([(0, {"x": 1}), (1, {"x": 2})])
    view = G.nodes(data="x")
    first_pass = list(view)
    second_pass = list(view)
    assert first_pass == second_pass


@needs_nx
def test_node_view_call_kwarg_form():
    """G.nodes(data=True) and G.nodes(True) should produce the same
    view contents."""
    G = fnx.Graph()
    G.add_nodes_from([(0, {"x": 1}), (1, {"x": 2})])
    via_kwarg = list(G.nodes(data=True))
    via_positional = list(G.nodes(True))
    assert via_kwarg == via_positional


@needs_nx
@pytest.mark.parametrize("cls_name", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
def test_nodes_data_true_index_preserves_live_attribute_dictionary(cls_name):
    for module in (nx, fnx):
        graph = getattr(module, cls_name)()
        graph.add_node(0, value=1)
        view = graph.nodes(data=True)
        attrs = view[0]
        assert attrs is graph.nodes[0] is dict(view)[0]
        attrs["value"] = 2
        assert graph.nodes[0]["value"] == 2
        graph.nodes[0]["other"] = 3
        assert view[0] == {"value": 2, "other": 3}


@needs_nx
@pytest.mark.parametrize("cls_name", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("view_first", [False, True])
def test_nodes_data_view_deepcopy_preserves_memo_cycles_and_shared_values(
    cls_name, view_first
):
    for module in (nx, fnx):
        graph = getattr(module, cls_name)()
        payload = [1]
        graph.add_nodes_from([(0, {"payload": payload}), (1, {"payload": payload})])
        view = graph.nodes(data=True)
        attrs = graph.nodes[0]
        attrs.update(view=view, self=attrs)
        source = [view, attrs] if view_first else [attrs, view]
        memo = {}
        result = copy.deepcopy(source, memo)
        copied, copied_attrs = result if view_first else reversed(result)
        assert type(copied) is type(view)
        assert copied[0] is copied_attrs is memo[id(attrs)]
        assert dict(copied)[0] is copied_attrs
        assert copied_attrs["self"] is copied_attrs
        assert copied_attrs["view"] is copied is memo[id(view)]
        assert copied_attrs["payload"] is copied[1]["payload"]
        assert copied_attrs["payload"] is not payload
        payload.append(2)
        assert copied_attrs["payload"] == [1]
        assert copy.copy(view)[0] is attrs


@needs_nx
@pytest.mark.parametrize("cls_name", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
def test_nodes_data_view_deepcopy_remaps_labels_selectors_and_defaults(cls_name):
    class Label:
        pass

    for module in (nx, fnx):
        graph = getattr(module, cls_name)()
        node, selector = Label(), Label()
        payload, default = [1], [9]
        graph.add_nodes_from([node, 1])
        graph.nodes[node][selector] = payload
        view = graph.nodes(data=selector, default=default)
        copied, copied_node, copied_selector, copied_payload, copied_default = (
            copy.deepcopy([view, node, selector, payload, default])
        )
        assert type(copied) is type(view)
        assert copied_node is not node
        assert copied_selector is not selector
        assert list(copied) == [(copied_node, copied_payload), (1, copied_default)]
        assert copied[copied_node] is copied_payload
        assert copied[1] is copied_default
        payload.append(2)
        default.append(8)
        assert copied_payload == [1]
        assert copied_default == [9]


@needs_nx
def test_nodes_data_view_deepcopy_propagates_attribute_copy_errors():
    class CannotCopy:
        def __deepcopy__(self, memo):
            raise ValueError("node data copy failed")

    for module in (nx, fnx):
        graph = module.Graph()
        graph.add_node(0, payload=CannotCopy())
        with pytest.raises(ValueError, match="^node data copy failed$"):
            copy.deepcopy(graph.nodes(data=True))
