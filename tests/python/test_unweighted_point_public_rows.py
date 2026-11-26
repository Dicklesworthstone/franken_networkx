"""Unweighted point searches use the same public row protocol as NetworkX."""

import networkx as nx
import pytest

import franken_networkx as fnx


QUERIES = ("bidirectional_shortest_path", "shortest_path", "shortest_path_length", "has_path")


def search(module, name, graph, target=3, **kwargs):
    try:
        return getattr(module, name)(graph, 0, target, **kwargs)
    except (nx.NetworkXNoPath, fnx.NetworkXNoPath):
        return "unreachable"


def with_public_rows(module, kind, connected):
    graph = getattr(module, kind)()
    graph.add_nodes_from(range(4))
    graph.add_edge(0, 3)
    # Force a reverse expansion after the first forward row. The predecessor
    # reader chooses 2 first although the forward row lists 1 first.
    rows = {0: {1: {}, 2: {}}, 1: {}, 2: {}, 3: {}}
    if graph.is_directed():
        pred = {0: {}, 1: {0: {}}, 2: {0: {}}, 3: {}}
        if connected:
            pred[3] = {2: {}, 1: {}}
            rows[1][3] = rows[2][3] = {}
        graph.pred, graph.succ = pred, rows
    else:
        rows[1][0] = rows[2][0] = {}
        if connected:
            rows[3] = {2: {}, 1: {}}
            rows[1][3] = rows[2][3] = {}
        graph.adj = rows
    return graph


@pytest.mark.parametrize("name", QUERIES)
@pytest.mark.parametrize("kind", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("connected", [False, True])
def test_point_search_observes_public_rows(name, kind, connected):
    oracle = with_public_rows(nx, kind, connected)
    expected = search(nx, name, oracle)
    assert search(fnx, name, with_public_rows(fnx, kind, connected)) == expected
    assert search(fnx, name, with_public_rows(nx, kind, connected)) == expected


@pytest.mark.parametrize("name", QUERIES)
def test_backend_observes_new_rows_after_cached_conversion(name):
    graph = nx.DiGraph([(0, 3), (1, 2)])
    nx.dijkstra_path_length(graph, 0, 3, backend="franken_networkx")
    assert graph.__networkx_cache__.get("backends", {}).get("franken_networkx")
    live = with_public_rows(nx, "DiGraph", True)
    graph.succ, graph.pred = live.succ, live.pred
    assert search(nx, name, graph, backend="franken_networkx") == search(nx, name, graph)


@pytest.mark.parametrize("name", QUERIES)
def test_public_reader_error_and_order(name):
    def run(module):
        reads = []

        class Graph(module.DiGraph):
            @property
            def pred(self):
                reads.append("pred")
                raise LookupError("public predecessors unavailable")

            @property
            def succ(self):
                reads.append("succ")
                raise AssertionError("successors read too early")

        graph = Graph()
        graph.add_edge(0, 3)
        with pytest.raises(LookupError, match="public predecessors unavailable"):
            search(module, name, graph)
        return reads

    assert run(nx) == run(fnx) == ["pred"]


@pytest.mark.parametrize("source,target", [(None, None), (0, None), (None, 0)])
def test_has_path_keeps_generic_endpoint_semantics(source, target):
    assert fnx.has_path(fnx.path_graph(3), source, target) == nx.has_path(
        nx.path_graph(3), source, target
    )


@pytest.mark.parametrize("kind", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
def test_ordinary_warm_views_still_use_native_point_search(kind, monkeypatch):
    graph = getattr(fnx, kind)()
    graph.add_edges_from([(0, 1), (1, 3)])
    if graph.is_directed():
        _ = graph.pred, graph.succ
    else:
        _ = graph.adj
    calls = []
    original = fnx._raw_bidirectional_shortest_path

    def counted(*args):
        calls.append(args)
        return original(*args)

    monkeypatch.setattr(fnx, "_raw_bidirectional_shortest_path", counted)
    assert fnx.shortest_path(graph, 0, 3) == [0, 1, 3]
    assert calls == [(graph, 0, 3)]
