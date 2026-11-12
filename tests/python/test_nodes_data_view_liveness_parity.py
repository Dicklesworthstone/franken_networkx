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
