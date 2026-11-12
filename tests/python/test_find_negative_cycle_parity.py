"""Parity coverage for find_negative_cycle.

Bead franken_networkx-94ld: the Rust implementation rejected directed
graphs with NetworkXNotImplemented; the Python wrapper routed directed
inputs through networkx's algorithm so both the success path and the
missing-source / no-cycle error contracts match upstream exactly.

nro4w.7: undirected graphs stayed on the native kernel, which returned a
valid negative cycle but not networkx's in 189 of 400 random graphs and
panicked (index usize::MAX) on a lone negative edge. Every graph now runs
networkx's detector in-process.
"""

import random
from decimal import Decimal
from fractions import Fraction

import networkx as nx
import pytest

import franken_networkx as fnx


def test_find_negative_cycle_directed_graph_matches_networkx():
    edges = [(0, 1, 1), (1, 2, -3), (2, 0, 1)]
    fg = fnx.DiGraph()
    fg.add_weighted_edges_from(edges)
    ng = nx.DiGraph()
    ng.add_weighted_edges_from(edges)

    f_cycle = fnx.find_negative_cycle(fg, 0)
    n_cycle = nx.find_negative_cycle(ng, 0)
    # Node list parity.
    assert f_cycle == n_cycle


def test_find_negative_cycle_directed_missing_source_matches_networkx():
    fg = fnx.DiGraph()
    fg.add_weighted_edges_from([(0, 1, -1), (1, 0, -1)])
    ng = nx.DiGraph()
    ng.add_weighted_edges_from([(0, 1, -1), (1, 0, -1)])

    with pytest.raises((fnx.NodeNotFound, nx.NodeNotFound), match="Source 99 not in G"):
        fnx.find_negative_cycle(fg, 99)
    with pytest.raises(nx.NodeNotFound, match="Source 99 not in G"):
        nx.find_negative_cycle(ng, 99)


def test_find_negative_cycle_directed_no_cycle_raises_networkx_error():
    fg = fnx.DiGraph()
    fg.add_weighted_edges_from([(0, 1, 1), (1, 2, 1)])
    ng = nx.DiGraph()
    ng.add_weighted_edges_from([(0, 1, 1), (1, 2, 1)])

    with pytest.raises(
        (fnx.NetworkXError, nx.NetworkXError), match="No negative cycles detected"
    ):
        fnx.find_negative_cycle(fg, 0)
    with pytest.raises(nx.NetworkXError, match="No negative cycles detected"):
        nx.find_negative_cycle(ng, 0)


@pytest.mark.parametrize("source", [0, 1])
def test_lone_negative_undirected_edge_matches_networkx(source):
    # networkx's own test_find_negative_cycle_single_edge; the native kernel
    # panicked here.
    G = fnx.Graph()
    G.add_edge(0, 1, weight=-1)
    H = nx.Graph()
    H.add_edge(0, 1, weight=-1)
    assert fnx.find_negative_cycle(G, source) == nx.find_negative_cycle(H, source)


def _outcome(module, cls_name, n, edges, source):
    G = getattr(module, cls_name)()
    G.add_nodes_from(range(n))
    G.add_weighted_edges_from(edges)
    try:
        return module.find_negative_cycle(G, source)
    except Exception as exc:  # the error contract is part of the parity
        return type(exc).__name__, str(exc)


@pytest.mark.parametrize("cls_name", ["Graph", "MultiGraph", "DiGraph", "MultiDiGraph"])
def test_random_graphs_return_networkx_cycle(cls_name):
    rng = random.Random(9)
    compared = 0
    for _ in range(300):
        n = rng.randint(2, 7)
        edges = [
            (rng.randrange(n), rng.randrange(n), rng.choice([-3, -1, 1, 2, 5]))
            for _ in range(rng.randint(1, 10))
        ]
        source = edges[0][0]
        expected = _outcome(nx, cls_name, n, edges, source)
        if expected[0] == "AttributeError":
            # Owned divergence: when the detected node carries a self-loop,
            # networkx evaluates ``weight(G, v, v)`` (graph passed as the
            # edge's ``u``) and crashes on ``int.get``. fnx evaluates the
            # self-loop's weight as networkx intends.
            continue
        compared += 1
        assert _outcome(fnx, cls_name, n, edges, source) == expected, (edges, source)
    assert compared > 250


def test_weights_written_after_construction_are_seen():
    # The scenario test_edge_attr_native_store_flush pinned on the removed
    # native binding: weights set through G[u][v] after add_edges_from.
    weights = {("a", "b"): -5.0, ("b", "c"): 1.0, ("a", "c"): 1.0}
    G = fnx.Graph()
    G.add_edges_from(list(weights))
    H = nx.Graph()
    H.add_edges_from(list(weights))
    for (u, v), w in weights.items():
        G[u][v]["weight"] = w
        H[u][v]["weight"] = w
    assert fnx.find_negative_cycle(G, "a") == nx.find_negative_cycle(H, "a")


def _live_weight_witness(graph_module, cls_name, algorithm):
    graph = getattr(graph_module, cls_name)()
    graph.add_weighted_edges_from(
        [(0, 1, 10), (0, 2, 1), (1, 4, 1), (2, 3, 1), (3, 1, 1), (4, 1, 1)]
    )
    trace = []

    def weight(u, v, data):
        trace.append((u, v))
        attrs = data[0] if graph.is_multigraph() else data
        original = graph._adj[u][v]
        original = original[0] if graph.is_multigraph() else original
        assert attrs is original
        if (u, v) == (1, 4) and trace.count((u, v)) == 2:
            attrs["weight"] = -20
        return attrs["weight"]

    cycle = algorithm(graph, 0, weight=weight)
    changed = graph[1][4][0] if graph.is_multigraph() else graph[1][4]
    return cycle, trace, changed["weight"]


@pytest.mark.parametrize("graph_module", [nx, fnx], ids=["foreign", "native"])
@pytest.mark.parametrize("cls_name", ["DiGraph", "MultiDiGraph"])
def test_revisited_rows_observe_new_weights(graph_module, cls_name):
    expected = _live_weight_witness(nx, cls_name, nx.find_negative_cycle)
    assert expected[0] == [1, 4, 1]
    assert expected[2] == -20
    assert _live_weight_witness(graph_module, cls_name, fnx.find_negative_cycle) == expected


@pytest.mark.parametrize("cached", [False, True])
@pytest.mark.parametrize("cls_name", ["DiGraph", "MultiDiGraph"])
def test_backend_witness_keeps_live_weights(cls_name, cached, monkeypatch):
    monkeypatch.setattr(nx.config, "cache_converted_graphs", True)

    def dispatched(graph, source, weight):
        if cached:
            nx.relabel_nodes(graph, {}, backend="franken_networkx")
            assert graph.__networkx_cache__["backends"]["franken_networkx"]
        answer = nx.find_negative_cycle(
            graph, source, weight=weight, backend="franken_networkx"
        )
        assert not graph.__networkx_cache__.get("backends")
        return answer

    assert _live_weight_witness(nx, cls_name, dispatched) == _live_weight_witness(
        nx, cls_name, nx.find_negative_cycle
    )


@pytest.mark.parametrize("graph_module", [nx, fnx], ids=["foreign", "native"])
@pytest.mark.parametrize("cls_name", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
def test_detection_stops_before_unused_outgoing_weight(graph_module, cls_name):
    graph = getattr(graph_module, cls_name)()
    graph.add_edge(0, 1, weight=-1)
    if graph.is_directed():
        graph.add_edge(1, 0, weight=-1)
    graph.add_edge(1, 2, weight=2)
    trace = []

    def weight(u, v, data):
        trace.append((u, v))
        if (u, v) == (1, 2):
            raise AssertionError("the cycle was already detected")
        return min(d["weight"] for d in data.values()) if graph.is_multigraph() else data["weight"]

    assert fnx.find_negative_cycle(graph, 0, weight=weight) == [0, 1, 0]
    assert trace == [(0, 1), (1, 0)]


@pytest.mark.parametrize("graph_module", [nx, fnx], ids=["foreign", "native"])
@pytest.mark.parametrize("cls_name", ["DiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("view", ["undirected", "filtered", "reverse"])
def test_witness_preserves_view_rows(graph_module, cls_name, view):
    def build(module):
        graph = getattr(module, cls_name)()
        graph.add_weighted_edges_from(
            [(0, 1, 1), (1, 0, 10), (1, 2, 1), (2, 1, 10), (2, 0, -5), (0, 2, 10)]
        )
        if view == "reverse":
            return graph.reverse(copy=False)
        graph = graph.to_undirected(as_view=True)
        return graph.subgraph([0, 1, 2]) if view == "filtered" else graph

    expected = nx.find_negative_cycle(build(nx), 0)
    assert fnx.find_negative_cycle(build(graph_module), 0) == expected


@pytest.mark.parametrize("graph_module", [nx, fnx], ids=["foreign", "native"])
@pytest.mark.parametrize("cls_name", ["DiGraph", "MultiDiGraph"])
def test_callback_topology_updates_reach_later_rows(graph_module, cls_name):
    def run(module, algorithm):
        graph = getattr(module, cls_name)()
        graph.add_weighted_edges_from([(0, 1, 1), (1, 2, 1)])
        trace = []

        def weight(u, v, data):
            trace.append((u, v))
            if (u, v) == (0, 1):
                graph.add_edge(2, 1, weight=-3)
            return min(d["weight"] for d in data.values()) if graph.is_multigraph() else data["weight"]

        return algorithm(graph, 0, weight=weight), trace, list(graph.edges())

    assert run(graph_module, fnx.find_negative_cycle) == run(nx, nx.find_negative_cycle)


@pytest.mark.parametrize("graph_module", [nx, fnx], ids=["foreign", "native"])
@pytest.mark.parametrize("cls_name", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("numeric", [Decimal, Fraction])
def test_exact_numeric_witnesses(graph_module, cls_name, numeric):
    edges = [(0, 1, numeric("0.1")), (1, 2, numeric("0.2")), (2, 0, numeric("-0.4"))]
    graph = getattr(graph_module, cls_name)()
    graph.add_weighted_edges_from(edges)
    expected = getattr(nx, cls_name)()
    expected.add_weighted_edges_from(edges)
    assert fnx.find_negative_cycle(graph, 0) == nx.find_negative_cycle(expected, 0)


@pytest.mark.parametrize("cls_name", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
def test_private_adjacency_is_authoritative_for_witness(cls_name):
    expected = getattr(nx, cls_name)()
    expected.add_weighted_edges_from([(0, 1, 1), (1, 2, -3), (2, 0, 1)])
    graph = getattr(fnx, cls_name)()
    graph.add_edge("stale", "native", weight=1)
    graph._node = expected._node
    graph._adj = expected._adj
    if expected.is_directed():
        graph._succ = expected._succ
        graph._pred = expected._pred
    assert fnx.find_negative_cycle(graph, 0) == nx.find_negative_cycle(expected, 0)


@pytest.mark.parametrize("cls_name", ["DiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("entrypoint", ["direct", "cold", "warm"])
def test_negative_cycle_predicate_keeps_foreign_attribute_identity(cls_name, entrypoint, monkeypatch):
    monkeypatch.setattr(nx.config, "cache_converted_graphs", True)
    def run(algorithm):
        graph = getattr(nx, cls_name)()
        graph.add_weighted_edges_from([(0, 1, 1), (1, 0, 1)])
        trace = []

        def weight(u, v, data):
            trace.append((u, v))
            attrs = data[0] if graph.is_multigraph() else data
            if u >= 0:
                original = graph._adj[u][v]
                assert attrs is (original[0] if graph.is_multigraph() else original)
            if (u, v) == (0, 1):
                changed = graph[1][0][0] if graph.is_multigraph() else graph[1][0]
                changed["weight"] = -3
            return attrs.get("weight", 1)

        result = algorithm(graph, weight=weight)
        return result, trace, list(graph.edges(data=True))

    def dispatched(graph, weight):
        if entrypoint == "direct":
            return fnx.negative_edge_cycle(graph, weight=weight)
        if entrypoint == "warm":
            nx.relabel_nodes(graph, {}, backend="franken_networkx")
            assert graph.__networkx_cache__["backends"]["franken_networkx"]
        result = nx.negative_edge_cycle(graph, weight=weight, backend="franken_networkx")
        assert not graph.__networkx_cache__.get("backends")
        return result

    assert run(dispatched) == run(nx.negative_edge_cycle)
