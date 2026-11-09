"""br-r37-c1-w7nn3: _fnx_to_nx must reproduce the source's adjacency
structure verbatim — row ORDER (directed pred rows followed the
succ-major emission walk, poisoning every delegated directed algorithm
sensitive to pred iteration: bidirectional searches returned the WRONG
tie-break path) and row OBJECTS (z6uka display overrides for mixed
hash-equal keys).
"""

import random

import networkx as nx
import pytest

import franken_networkx as fnx
from franken_networkx.backend import _fnx_to_nx

CLASSES = ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"]


def _rows(g):
    out = {repr(n): [repr(x) for x in g.adj[n]] for n in g}
    if g.is_directed():
        out["__pred__"] = {repr(n): [repr(x) for x in g.pred[n]] for n in g}
    return out


@pytest.mark.parametrize("cls", CLASSES)
def test_conversion_rows_match_native_nx(cls):
    gf, gn = getattr(fnx, cls)(), getattr(nx, cls)()
    for g in (gf, gn):
        g.add_node(28)
        g.add_edge("s", "a")
        g.add_edge("s", "b")
        g.add_edge("b", "t")
        g.add_edge("a", "t")
        g.add_edge(7, 28.0)
        if g.is_multigraph():
            g.add_edge("s", "a", w=9)
    assert _rows(_fnx_to_nx(gf)) == _rows(gn)


@pytest.mark.parametrize("cls", CLASSES)
def test_conversion_random_corpus(cls):
    rnd = random.Random(17)
    for trial in range(15):
        gf, gn = getattr(fnx, cls)(), getattr(nx, cls)()
        for _ in range(rnd.randrange(2, 50)):
            u, v = rnd.randrange(12), rnd.randrange(12)
            gf.add_edge(u, v, w=u)
            gn.add_edge(u, v, w=u)
        assert _rows(_fnx_to_nx(gf)) == _rows(gn), trial


def test_succ_pred_datadict_sharing_survives_alignment():
    gf = fnx.DiGraph()
    gf.add_edge("s", "a", w=1)
    gf.add_edge("b", "a", w=2)
    conv = _fnx_to_nx(gf)
    conv.succ["s"]["a"]["w"] = 99
    assert conv.pred["a"]["s"]["w"] == 99
    gu = fnx.Graph()
    gu.add_edge("s", "a", w=1)
    convu = _fnx_to_nx(gu)
    convu.adj["s"]["a"]["w"] = 99
    assert convu.adj["a"]["s"]["w"] == 99


def test_delegated_bidirectional_tie_break_no_longer_poisoned():
    gf, gn = fnx.DiGraph(), nx.DiGraph()
    for g in (gf, gn):
        g.add_edge("s", "a")
        g.add_edge("s", "b")
        g.add_edge("b", "t")
        g.add_edge("a", "t")
    assert nx.bidirectional_shortest_path(
        _fnx_to_nx(gf), "s", "t"
    ) == nx.bidirectional_shortest_path(gn, "s", "t")


def _assigned_conversion_graph(module, graph_class, assignment):
    graph = getattr(module, graph_class)()
    graph.add_nodes_from([0, 1, 2, 3])
    graph.add_edges_from([(0, 1), (1, 2), (2, 3)])
    graph.graph["payload"] = {"version": 1}
    if assignment in ("adjacency", "both"):
        rows = getattr(nx, graph_class)()
        rows.add_nodes_from(graph)
        # Predecessor order at 2 differs from successor-major edge order.
        for u, v in [(3, 2), (0, 2), (1, 2), (1, 3), (2, 2)]:
            rows.add_edge(u, v, capacity=u + 2, nested={"source": u})
        if graph.is_multigraph():
            rows.add_edge(3, 2, key=("parallel", 0), capacity=9, nested={"source": 3})
        graph._adj = rows._adj
        if graph.is_directed():
            graph._pred = rows._pred
    if assignment in ("nodes", "both"):
        # The native node order is still 0,1,2,3. A zip against a bulk
        # snapshot must not reinterpret those IDs as 3,2,1,0.
        graph._node = {
            node: {"label": f"private-{node}"} for node in reversed(list(graph))
        }
    return graph


def _assert_converted_storage(actual, source):
    assert actual.is_directed() == source.is_directed()
    assert actual.is_multigraph() == source.is_multigraph()
    assert list(actual.nodes(data=True)) == list(source.nodes(data=True))
    assert actual.graph == source.graph
    assert _rows(actual) == _rows(source)
    assert list(actual.adj) == list(source.adj)
    if source.is_directed():
        assert list(actual.pred) == list(source.pred)
    if source.is_multigraph():
        assert list(actual.edges(keys=True, data=True)) == list(source.edges(keys=True, data=True))
    else:
        assert list(actual.edges(data=True)) == list(source.edges(data=True))
    for u in source:
        for v, data in source.adj[u].items():
            if source.is_multigraph():
                assert list(actual[u][v]) == list(data)
                for key, attrs in data.items():
                    converted = actual[u][v][key]
                    assert converted == attrs and converted is not attrs
                    if source.is_directed():
                        assert actual.pred[v][u][key] is converted
                    else:
                        assert actual[v][u][key] is converted
            else:
                converted = actual[u][v]
                assert converted == data and converted is not data
                if source.is_directed():
                    assert actual.pred[v][u] is converted
                else:
                    assert actual[v][u] is converted


@pytest.mark.parametrize("graph_class", CLASSES)
@pytest.mark.parametrize("assignment", ["adjacency", "nodes", "both"])
def test_conversion_uses_assigned_storage_and_live_attributes(graph_class, assignment):
    graph = _assigned_conversion_graph(fnx, graph_class, assignment)
    reference = _assigned_conversion_graph(nx, graph_class, assignment)
    _assert_converted_storage(_fnx_to_nx(graph), reference)

    # Mutations through escaped attribute dictionaries must remain visible
    # on later conversions without changing the logical node or row order.
    for source in (graph, reference):
        source.nodes[0]["updated"] = True
        edge = next(iter(source.edges(keys=True) if source.is_multigraph() else source.edges()))
        source.edges[edge]["capacity"] = 37
    _assert_converted_storage(_fnx_to_nx(graph), reference)


@pytest.mark.parametrize("graph_class", ["DiGraph", "MultiDiGraph"])
def test_conversion_uses_assigned_predecessor_order(graph_class):
    graphs = []
    for module in (fnx, nx):
        graph = getattr(module, graph_class)([(2, 3), (0, 3), (1, 3)])
        graph._pred = {
            node: dict(reversed(list(graph.pred[node].items())))
            for node in reversed(list(graph))
        }
        graphs.append(graph)
    _assert_converted_storage(_fnx_to_nx(graphs[0]), graphs[1])


@pytest.mark.parametrize("graph_class", CLASSES)
def test_conversion_preserves_assigned_outer_row_key_identity(graph_class):
    graph = getattr(fnx, graph_class)()
    graph.add_nodes_from([1, 2])
    logical = getattr(nx, graph_class)()
    logical.add_edge(1.0, 2.0, capacity=7)
    graph._adj = logical._adj
    if graph.is_directed():
        graph._pred = logical._pred

    converted = _fnx_to_nx(graph)
    assert [type(node) for node in converted] == [int, int]
    for accessor in (("adj", "pred") if graph.is_directed() else ("adj",)):
        expected_keys = list(getattr(graph, accessor))
        actual_keys = list(getattr(converted, accessor))
        assert [type(node) for node in expected_keys] == [float, float]
        assert len(actual_keys) == len(expected_keys)
        assert all(actual is expected for actual, expected in zip(actual_keys, expected_keys))


@pytest.mark.parametrize("graph_class", ["Graph", "DiGraph", "MultiDiGraph"])
def test_conversion_keeps_native_bulk_routes_only_for_native_storage(monkeypatch, graph_class):
    import franken_networkx.backend as backend

    calls = []
    if graph_class == "MultiDiGraph":
        original = fnx.MultiDiGraph._native_predecessor_keys_bulk

        def recorded(graph):
            calls.append(graph)
            return original(graph)

        monkeypatch.setattr(fnx.MultiDiGraph, "_native_predecessor_keys_bulk", recorded)
    else:
        original = backend._native_fnx_to_nx_adjacency

        def recorded(graph):
            calls.append(graph)
            return original(graph)

        monkeypatch.setattr(backend, "_native_fnx_to_nx_adjacency", recorded)

    graph = getattr(fnx, graph_class)([(0, 1), (1, 2)])
    _assert_converted_storage(_fnx_to_nx(graph), graph)
    assert calls == [graph]
    private = _assigned_conversion_graph(fnx, graph_class, "both")
    _assert_converted_storage(_fnx_to_nx(private), private)
    assert calls == [graph]
