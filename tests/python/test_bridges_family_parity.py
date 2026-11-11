"""Differential + golden parity for ``has_bridges`` / ``local_bridges``.

``has_bridges(G)`` is a boolean; ``local_bridges(G, with_span=...)`` yields
local-bridge edges (optionally with their span). ``bridges`` itself already
has coverage.

br-r37-c1-vrdid
"""

from __future__ import annotations

import random

import pytest
import networkx as nx
import franken_networkx as fnx


def _connected(seed, p=0.35):
    rng = random.Random(seed)
    n = rng.randint(5, 10)
    p_cur = p
    for _ in range(60):
        fg = fnx.Graph()
        ng = nx.Graph()
        fg.add_nodes_from(range(n))
        ng.add_nodes_from(range(n))
        for u in range(n):
            for v in range(u + 1, n):
                if rng.random() < p_cur:
                    fg.add_edge(u, v)
                    ng.add_edge(u, v)
        if nx.is_connected(ng):
            return fg, ng
        p_cur = min(0.9, p_cur + 0.05)
    return None


def _span_set(edges):
    return {(tuple(sorted((e[0], e[1]))), e[2]) for e in edges}


def _edge_set(edges):
    return {tuple(sorted((e[0], e[1]))) for e in edges}


@pytest.mark.parametrize("seed", range(60))
def test_has_bridges_matches_networkx(seed):
    pair = _connected(seed)
    if pair is None:
        pytest.skip("no connected graph")
    fg, ng = pair
    assert fnx.has_bridges(fg) == nx.has_bridges(ng)


@pytest.mark.parametrize("seed", range(60))
def test_local_bridges_matches_networkx(seed):
    pair = _connected(seed)
    if pair is None:
        pytest.skip("no connected graph")
    fg, ng = pair
    assert _span_set(fnx.local_bridges(fg)) == _span_set(nx.local_bridges(ng))
    assert _edge_set(fnx.local_bridges(fg, with_span=False)) == _edge_set(
        nx.local_bridges(ng, with_span=False)
    )


def test_bridges_goldens():
    # Every edge of a path is a bridge; a cycle has none.
    assert fnx.has_bridges(fnx.path_graph(4))
    assert not fnx.has_bridges(fnx.cycle_graph(4))
    # In a tree every edge is a local bridge with infinite span.
    p4 = fnx.path_graph(4)
    assert _span_set(fnx.local_bridges(p4)) == {
        ((0, 1), float("inf")), ((1, 2), float("inf")), ((2, 3), float("inf"))
    }


# br-r37-c1-64xcg: local_bridges(weight=...) ran its own Dijkstra on a
# (distance, node) heap, so a distance tie compared two nodes - TypeError on
# mixed int / str labels, where networkx's heap breaks ties with a counter.
@pytest.mark.parametrize("weight", [None, "weight", lambda u, v, d: d.get("weight", 1)])
@pytest.mark.parametrize("with_span", [True, False])
def test_local_bridges_on_mixed_labels_matches_networkx(with_span, weight):
    edges = [(0, "n1", 1.5), ("n1", 2, 2.5), (2, "n3", 1.0), ("n3", 0, 2.0), (2, "n5", 1.0),
             ("n5", 6, 0.5), (6, "n7", 1.5), ("n7", 0, 3.0), ("n5", 8, 2.0), (8, "n9", 1.0)]

    def bridges(lib):
        g = lib.Graph()
        g.add_weighted_edges_from(edges)
        return list(lib.local_bridges(g, with_span=with_span, weight=weight))

    assert bridges(fnx) == bridges(nx)


@pytest.mark.parametrize("graph_library", [nx, fnx])
@pytest.mark.parametrize("multigraph", [False, True])
@pytest.mark.parametrize("root", [None, 0])
def test_bridges_read_graph_when_iteration_starts(graph_library, multigraph, root):
    cls_name = "MultiGraph" if multigraph else "Graph"
    graph = getattr(graph_library, cls_name)([(0, 1), (1, 2)])
    expected = getattr(nx, cls_name)([(0, 1), (1, 2)])
    iterator = fnx.bridges(graph, root=root)
    graph.add_edge(2, 0)
    expected.add_edge(2, 0)
    assert list(iterator) == list(nx.bridges(expected, root=root)) == []


@pytest.mark.parametrize("root", [None, 0])
@pytest.mark.parametrize("mutation", ["remove_edge", "parallel_edge"])
def test_bridges_read_remaining_edges_after_a_yield(root, mutation):
    def run(library):
        graph = nx.MultiGraph() if mutation == "parallel_edge" else nx.Graph()
        graph.add_edges_from([(0, 1), (1, 2), (2, 3)])
        iterator = library.bridges(graph, root=root)
        first = next(iterator)
        if mutation == "parallel_edge":
            graph.add_edge(2, 3)
        else:
            graph.remove_edge(2, 3)
        return first, list(iterator)

    assert run(fnx) == run(nx)


def test_bridges_observe_changed_view_filter_before_iteration():
    graph = nx.cycle_graph(4)
    hidden = {(3, 0), (0, 3)}
    view = nx.subgraph_view(graph, filter_edge=lambda u, v: (u, v) not in hidden)
    iterator = fnx.bridges(view)
    hidden.clear()
    assert list(iterator) == list(nx.bridges(view)) == []


def test_bridges_root_validation_waits_for_iteration():
    graph = nx.Graph([(0, 1)])
    iterator = fnx.bridges(graph, root=2)
    graph.add_edge(1, 2)
    assert list(iterator) == list(nx.bridges(graph, root=2))
    missing = fnx.bridges(graph, root=9)
    with pytest.raises(nx.NodeNotFound, match="Root node 9 is not in graph"):
        next(missing)


@pytest.mark.parametrize("graph_library", [nx, fnx])
@pytest.mark.parametrize("with_span", [True, False])
def test_local_bridges_read_graph_when_iteration_starts(graph_library, with_span):
    graph = graph_library.Graph([(0, 1), (1, 2)])
    iterator = fnx.local_bridges(graph, with_span=with_span)
    graph.add_edge(2, 0)
    assert list(iterator) == []


@pytest.mark.parametrize("with_span", [True, False])
def test_local_bridges_read_remaining_rows_after_a_yield(with_span):
    def run(library):
        graph = nx.path_graph(5)
        iterator = library.local_bridges(graph, with_span=with_span)
        first = next(iterator)
        graph.add_edge(2, 4)
        return first, list(iterator)

    assert run(fnx) == run(nx)


@pytest.mark.parametrize("with_span", [None, 0, 1, "yes", [], object()])
def test_local_bridges_only_literal_true_requests_spans(with_span):
    graph = nx.path_graph(3)
    assert list(fnx.local_bridges(graph, with_span=with_span)) == list(
        nx.local_bridges(graph, with_span=with_span)
    )


@pytest.mark.parametrize("graph_library", [nx, fnx])
@pytest.mark.parametrize("weight_key", [None, "cost", ("cost", 0)])
def test_local_bridges_preserve_weight_keys_and_exact_span_types(graph_library, weight_key):
    from decimal import Decimal
    from fractions import Fraction

    for value in (Decimal("1.5"), Fraction(3, 2), 2**1000):
        graph = graph_library.Graph([(0, 1), (1, 2), (2, 3), (3, 0)])
        expected = nx.Graph([(0, 1), (1, 2), (2, 3), (3, 0)])
        for u, v in expected.edges:
            graph[u][v][weight_key] = value
            expected[u][v][weight_key] = value
        actual = list(fnx.local_bridges(graph, weight=weight_key))
        wanted = list(nx.local_bridges(expected, weight=weight_key))
        assert actual == wanted
        assert [type(span) for _, _, span in actual] == [
            type(span) for _, _, span in wanted
        ]


def test_local_bridges_weight_callbacks_keep_live_dicts_and_defer_errors():
    def run(library):
        graph = nx.cycle_graph(4)
        nx.set_edge_attributes(graph, 1, "weight")
        calls = []

        def weight(u, v, data):
            assert data is graph._adj[u][v]
            calls.append((u, v))
            if (u, v) == (0, 3):
                graph[3][2]["weight"] = 7
            return data["weight"]

        iterator = library.local_bridges(graph, weight=weight)
        assert calls == []
        return list(iterator), calls

    assert run(fnx) == run(nx)

    failure = RuntimeError("weight failed on the caller's graph")

    def fail_weight(u, v, data):
        raise failure

    iterator = fnx.local_bridges(nx.cycle_graph(4), weight=fail_weight)
    with pytest.raises(RuntimeError) as error:
        next(iterator)
    assert error.value is failure
