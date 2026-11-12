"""Parity for ``Graph.edges(nbunch)`` iteration order.

Bead br-r37-c1-dc14n. fnx.Graph.edges(nbunch) returned edges in
G.nodes()-iteration order filtered by nbunch — not nx's contract.
nx walks nbunch in user-given order, then for each node yields
edges (u, v) in adj[u] order, skipping edges where v has already
been visited.

Repro:
  edges = [('c','d'),('a','b'),('b','c'),('d','e'),('a','c')]
  Both libs: adj['a'] = ['b','c'], adj['b'] = ['a','c']

  fnx.edges(['a','b']) -> [('b','c'), ('a','c'), ('a','b')]
  nx .edges(['a','b']) -> [('a','b'), ('a','c'), ('b','c')]

DiGraph (with separate _DiGraphEdgeView Python class) was already
correct.

Fix: register the Graph in a per-process EdgeView->Graph map when
g.edges is accessed; EdgeDataView reads it back to walk adj in
user-given nbunch order.
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


def _make_graph(lib, edges):
    g = lib.Graph()
    for u, v in edges:
        g.add_edge(u, v)
    return g


@needs_nx
def test_edges_nbunch_two_nodes_matches_nx():
    edges = [("c", "d"), ("a", "b"), ("b", "c"), ("d", "e"), ("a", "c")]
    g = _make_graph(fnx, edges)
    gx = _make_graph(nx, edges)
    assert list(g.edges(["a", "b"])) == list(gx.edges(["a", "b"]))


@needs_nx
def test_edges_nbunch_user_order_respected():
    """nbunch = ['b', 'a'] should yield b's edges first."""
    edges = [("c", "d"), ("a", "b"), ("b", "c"), ("d", "e"), ("a", "c")]
    g = _make_graph(fnx, edges)
    gx = _make_graph(nx, edges)
    assert list(g.edges(["b", "a"])) == list(gx.edges(["b", "a"]))


@needs_nx
def test_edges_single_node_str():
    edges = [("c", "d"), ("a", "b"), ("b", "c"), ("d", "e"), ("a", "c")]
    g = _make_graph(fnx, edges)
    gx = _make_graph(nx, edges)
    assert list(g.edges("a")) == list(gx.edges("a"))


@needs_nx
def test_edges_three_node_nbunch_matches_nx():
    edges = [("c", "d"), ("a", "b"), ("b", "c"), ("d", "e"), ("a", "c")]
    g = _make_graph(fnx, edges)
    gx = _make_graph(nx, edges)
    assert list(g.edges(["a", "b", "c"])) == list(gx.edges(["a", "b", "c"]))


@needs_nx
def test_edges_int_nodes_path_matches_nx():
    g = fnx.path_graph(5)
    gx = nx.path_graph(5)
    assert list(g.edges([1, 2, 3])) == list(gx.edges([1, 2, 3]))


@needs_nx
def test_edges_with_data_kwarg_matches_nx():
    edges = [("c", "d", 1), ("a", "b", 2), ("b", "c", 3)]
    g = fnx.Graph()
    gx = nx.Graph()
    for u, v, w in edges:
        g.add_edge(u, v, weight=w)
        gx.add_edge(u, v, weight=w)
    assert list(g.edges(["a", "b"], data=True)) == list(gx.edges(["a", "b"], data=True))


@needs_nx
def test_edges_with_data_str_kwarg_matches_nx():
    edges = [("c", "d", 1), ("a", "b", 2), ("b", "c", 3)]
    g = fnx.Graph()
    gx = nx.Graph()
    for u, v, w in edges:
        g.add_edge(u, v, weight=w)
        gx.add_edge(u, v, weight=w)
    assert list(g.edges(["a", "b"], data="weight")) == list(
        gx.edges(["a", "b"], data="weight")
    )


@needs_nx
def test_edges_nbunch_with_default_attr_matches_nx():
    g = fnx.Graph([("a", "b"), ("b", "c")])
    gx = nx.Graph([("a", "b"), ("b", "c")])
    assert list(g.edges(["a"], data="weight", default=99)) == list(
        gx.edges(["a"], data="weight", default=99)
    )


@needs_nx
def test_edges_no_nbunch_unchanged():
    """All-edges case (no nbunch) was already correct; verify we
    didn't regress it."""
    edges = [("c", "d"), ("a", "b"), ("b", "c"), ("d", "e"), ("a", "c")]
    g = _make_graph(fnx, edges)
    gx = _make_graph(nx, edges)
    assert list(g.edges()) == list(gx.edges())


@needs_nx
def test_edges_nbunch_missing_node_skipped_silently():
    """nx silently skips nbunch nodes not in G."""
    g = fnx.Graph([("a", "b"), ("b", "c")])
    gx = nx.Graph([("a", "b"), ("b", "c")])
    assert list(g.edges(["a", "missing", "b"])) == list(
        gx.edges(["a", "missing", "b"])
    )


@needs_nx
def test_edges_nbunch_full_node_set_matches_all_edges():
    """nbunch covering all nodes should match the full edge view
    iteration order."""
    edges = [("c", "d"), ("a", "b"), ("b", "c"), ("d", "e"), ("a", "c")]
    g = _make_graph(fnx, edges)
    gx = _make_graph(nx, edges)
    nodes = list(g.nodes())
    assert list(g.edges(nodes)) == list(gx.edges(nodes))


@needs_nx
def test_edges_directed_unchanged():
    """DiGraph already matched nx — sanity check we didn't regress."""
    dg = fnx.DiGraph()
    dgx = nx.DiGraph()
    for u, v in [("c", "d"), ("a", "b"), ("b", "c"), ("d", "a"), ("c", "a")]:
        dg.add_edge(u, v)
        dgx.add_edge(u, v)
    assert list(dg.edges(["c", "a"])) == list(dgx.edges(["c", "a"]))
    assert list(dg.out_edges(["c", "a"])) == list(dgx.out_edges(["c", "a"]))
    assert list(dg.in_edges(["c", "a"])) == list(dgx.in_edges(["c", "a"]))


@needs_nx
@pytest.mark.parametrize("class_name", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("nbunch", [None, 2, [2, 1], [2, 99, 1, 2]])
@pytest.mark.parametrize("selector", ["cost", 7, ("cost", 0), 0, 1, 0.0])
def test_attribute_selectors_preserve_nbunch_orientation_and_order(class_name, nbunch, selector):
    graphs = getattr(fnx, class_name)(), getattr(nx, class_name)()
    for graph in graphs:
        graph.add_nodes_from(range(4))
        for index, (u, v) in enumerate([(0, 2), (1, 2), (2, 3), (2, 2)]):
            attrs = {
                "cost": index, 7: index + 10, ("cost", 0): index + 20,
                0: index + 30, 1: index + 40,
            }
            graph.add_edges_from([(u, v, attrs)])
        if graph.is_multigraph():
            graph.add_edges_from([(0, 2, {selector: "parallel"})])
    views = ["edges"]
    if graphs[0].is_directed():
        views.extend(["out_edges", "in_edges"])
    for name in views:
        expected = list(getattr(graphs[1], name)(nbunch, data=selector, default="missing"))
        view = getattr(graphs[0], name)(nbunch, data=selector, default="missing")
        assert list(view) == expected
        assert list(iter(view)) == expected


@needs_nx
@pytest.mark.parametrize("class_name", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("selector", ["cost", 7, ("cost", 0), 0, 1, 0.0])
def test_attribute_selectors_read_current_row_values_when_yielded(class_name, selector):
    accessors = ["edges"]
    if "DiGraph" in class_name:
        accessors.extend(["out_edges", "in_edges"])

    def run(module, accessor):
        graph = getattr(module, class_name)()
        endpoints = [(0, 1), (0, 2)]
        if accessor == "in_edges":
            endpoints = [(target, source) for source, target in endpoints]
        graph.add_edges_from([(u, v, {selector: index}) for index, (u, v) in enumerate(endpoints)])
        iterator = iter(getattr(graph, accessor)(0, data=selector))
        first = next(iterator)
        attrs = graph.get_edge_data(*endpoints[1])
        if graph.is_multigraph():
            attrs = attrs[0]
        attrs[selector] = 99
        return first, list(iterator)

    for accessor in accessors:
        expected = run(nx, accessor)
        assert expected[1][0][-1] == 99
        assert run(fnx, accessor) == expected
