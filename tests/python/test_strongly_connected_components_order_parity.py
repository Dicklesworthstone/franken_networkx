"""Parity for ``strongly_connected_components`` emission order.

Bead br-r37-c1-2vdtt. The previous wrapper applied ``reversed()`` to
the Rust binding's output to flip source-first into sink-first order.
That heuristic only matched nx for small symmetric inputs; on multi-
component DiGraphs where Rust's DFS start node differs from nx's, the
flipped order disagreed with nx's Tarjan-discovery contract.

The owned iterative search must preserve both component emission order and
the iteration order of each member set. The latter also selects cycle pivots
and remains observable when integer node hashes collide (br-r37-c1-ra7sv).
"""

from __future__ import annotations

import random

import pytest

import franken_networkx as fnx

try:
    import networkx as nx
    HAS_NX = True
except ImportError:
    HAS_NX = False

needs_nx = pytest.mark.skipif(not HAS_NX, reason="networkx not installed")


def _make_dg(lib, edges):
    g = lib.DiGraph()
    for u, v in edges:
        g.add_edge(u, v)
    return g


@needs_nx
def test_two_components_str_nodes_match_nx():
    """Repro from the bead description."""
    edges = [
        ("c", "d"), ("a", "b"), ("b", "c"), ("d", "a"),
        ("c", "a"), ("e", "f"), ("f", "e"),
    ]
    g = _make_dg(fnx, edges)
    gx = _make_dg(nx, edges)
    f = list(fnx.strongly_connected_components(g))
    n = list(nx.strongly_connected_components(gx))
    assert f == n


@needs_nx
def test_disjoint_two_cycles_match_nx():
    edges = [("a", "b"), ("b", "a"), ("c", "d"), ("d", "c")]
    g = _make_dg(fnx, edges)
    gx = _make_dg(nx, edges)
    f = list(fnx.strongly_connected_components(g))
    n = list(nx.strongly_connected_components(gx))
    assert f == n


@needs_nx
def test_three_node_cycle_with_attached_pair_match_nx():
    edges = [("a", "b"), ("b", "c"), ("c", "a"), ("d", "e"), ("e", "d"), ("a", "d")]
    g = _make_dg(fnx, edges)
    gx = _make_dg(nx, edges)
    f = list(fnx.strongly_connected_components(g))
    n = list(nx.strongly_connected_components(gx))
    assert f == n


@needs_nx
def test_int_nodes_match_nx():
    edges = [("0", "1"), ("1", "0"), ("2", "3"), ("3", "2"), ("0", "2")]
    g = _make_dg(fnx, edges)
    gx = _make_dg(nx, edges)
    f = list(fnx.strongly_connected_components(g))
    n = list(nx.strongly_connected_components(gx))
    assert f == n


@needs_nx
def test_single_component_match_nx():
    edges = [(0, 1), (1, 2), (2, 0)]
    g = _make_dg(fnx, edges)
    gx = _make_dg(nx, edges)
    f = list(fnx.strongly_connected_components(g))
    n = list(nx.strongly_connected_components(gx))
    assert f == n


@needs_nx
def test_dag_each_node_own_component():
    edges = [(0, 1), (1, 2), (2, 3)]
    g = _make_dg(fnx, edges)
    gx = _make_dg(nx, edges)
    f = list(fnx.strongly_connected_components(g))
    n = list(nx.strongly_connected_components(gx))
    assert f == n


@needs_nx
def test_undirected_input_raises_not_implemented():
    """fnx mirrors nx's ``@not_implemented_for('undirected')`` error."""
    g = fnx.Graph([(1, 2), (2, 3)])
    with pytest.raises(fnx.NetworkXNotImplemented, match="undirected"):
        list(fnx.strongly_connected_components(g))


@needs_nx
def test_empty_digraph():
    g = fnx.DiGraph()
    gx = nx.DiGraph()
    f = list(fnx.strongly_connected_components(g))
    n = list(nx.strongly_connected_components(gx))
    assert f == n == []


@needs_nx
def test_isolated_nodes_each_their_own_component():
    g = fnx.DiGraph()
    gx = nx.DiGraph()
    for n in ["a", "b", "c"]:
        g.add_node(n)
        gx.add_node(n)
    f = list(fnx.strongly_connected_components(g))
    n_ = list(nx.strongly_connected_components(gx))
    assert f == n_


def _scc_for_input_route(graph, route):
    if route == "backend":
        return nx.strongly_connected_components(graph, backend="franken_networkx")
    return fnx.strongly_connected_components(graph)


@needs_nx
@pytest.mark.parametrize("cls_name", ["DiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("route", ["native-input", "networkx-input", "backend"])
@pytest.mark.parametrize("view_kind", ["graph", "subgraph", "filter"])
def test_member_sets_follow_root_then_completed_branch_order(cls_name, route, view_kind):
    actual_lib = fnx if route == "native-input" else nx
    actual, expected = getattr(actual_lib, cls_name)(), getattr(nx, cls_name)()
    for graph in (actual, expected):
        graph.add_nodes_from([0, 1024, 2048, 3072, 8192, 8200, 9999])
        graph.add_edges_from([
            (0, 1024), (1024, 2048), (2048, 0),
            (1024, 3072), (3072, 0),
            (0, 8192), (8192, 8200), (8200, 8192),
        ])

    def view(lib, graph):
        if view_kind == "subgraph":
            return graph.subgraph(list(graph))
        if view_kind == "filter":
            return lib.subgraph_view(graph, filter_node=lambda node: True)
        return graph

    want = [list(component) for component in nx.strongly_connected_components(
        view(nx, expected)
    )]
    got = [list(component) for component in _scc_for_input_route(
        view(actual_lib, actual), route
    )]
    assert got == want


@needs_nx
@pytest.mark.parametrize("cls_name", ["DiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("route", ["native-input", "networkx-input", "backend"])
def test_random_component_member_order_with_colliding_hashes(cls_name, route):
    actual_lib = fnx if route == "native-input" else nx
    for seed in range(24):
        rng = random.Random(seed)
        nodes = [1024 * node for node in rng.sample(range(32), 32)]
        edges = [(u, v) for u in nodes for v in nodes if rng.random() < 0.09]
        actual, expected = getattr(actual_lib, cls_name)(), getattr(nx, cls_name)()
        for graph in (actual, expected):
            graph.add_nodes_from(nodes)
            graph.add_edges_from(edges)
        want = [list(component) for component in nx.strongly_connected_components(expected)]
        got = [list(component) for component in _scc_for_input_route(actual, route)]
        assert got == want, (cls_name, route, seed)


@needs_nx
@pytest.mark.parametrize("route", ["networkx-input", "backend"])
def test_member_order_preserves_lazy_prefix_and_yielded_set_independence(route):
    graph = nx.DiGraph()
    graph.add_nodes_from([0, 8, 1024, 1032, 9999])
    graph.add_edges_from([(0, 8), (8, 0), (1024, 1032), (1032, 1024)])
    expected = [list(component) for component in nx.strongly_connected_components(graph)]
    reads = []
    allowed = {0, 8}

    class PrefixRows(dict):
        def __getitem__(self, node):
            reads.append(node)
            assert node in allowed, "SCC prefix read an unrequested component"
            return super().__getitem__(node)

    graph._adj = PrefixRows(graph._adj)
    iterator = _scc_for_input_route(graph, route)
    assert reads == []
    first = next(iterator)
    assert list(first) == expected[0]
    assert set(reads) == {0, 8}
    first.clear()
    allowed.update(graph)
    assert [list(component) for component in iterator] == expected[1:]
