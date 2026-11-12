"""Bellman-Ford predecessor mode, early cycle detection, and full-map targets."""

from decimal import Decimal
from fractions import Fraction
import math
import random

import networkx as nx
import pytest

import franken_networkx as fnx


GRAPH_TYPES = ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"]


def _ordered_typed(value):
    if isinstance(value, dict):
        return [(key, _ordered_typed(item)) for key, item in value.items()]
    if isinstance(value, (tuple, list)):
        return type(value).__name__, [_ordered_typed(item) for item in value]
    return type(value).__name__, repr(value)


def _outcome(module, graph, source=0, **options):
    try:
        result = module.bellman_ford_predecessor_and_distance(graph, source, **options)
    except Exception as error:
        return "raise", type(error).__name__, str(error)
    return "return", _ordered_typed(result)


def _weight_callback(graph, events):
    def weight(u, v, data):
        events.append((u, v))
        if graph.is_multigraph():
            return min(attrs.get("weight", 1) for attrs in data.values())
        return data.get("weight", 1)

    return weight


@pytest.mark.parametrize("graph_type", GRAPH_TYPES)
@pytest.mark.parametrize("heuristic", [False, True])
@pytest.mark.parametrize("callable_weight", [False, True])
@pytest.mark.parametrize("cost", [-1e308, -math.inf])
def test_requested_heuristic_detects_cycles_before_float_saturation(
    graph_type, heuristic, callable_weight, cost
):
    observations = []
    for module in (fnx, nx):
        graph = getattr(module, graph_type)()
        graph.add_nodes_from(range(12))
        graph.add_edge(0, 1, weight=cost)
        if graph.is_directed():
            graph.add_edge(1, 0, weight=1)
        weight = _weight_callback(graph, []) if callable_weight else "weight"
        observations.append(_outcome(module, graph, weight=weight, heuristic=heuristic))
    assert observations[0] == observations[1]
    if heuristic:
        assert observations[1] == ("raise", "NetworkXUnbounded", "Negative cycle detected.")
    else:
        assert observations[1][0] == "return"


@pytest.mark.parametrize("graph_type", GRAPH_TYPES)
@pytest.mark.parametrize("heuristic", [False, True])
@pytest.mark.parametrize("size", [16, 256, 2048])
def test_early_detection_does_not_repeat_relaxations_for_isolated_nodes(
    graph_type, heuristic, size
):
    observations = []
    for module in (fnx, nx):
        graph = getattr(module, graph_type)()
        graph.add_nodes_from(range(size))
        graph.add_edge(0, 1, weight=-1)
        if graph.is_directed():
            graph.add_edge(1, 0, weight=0)
        events = []
        result = _outcome(
            module, graph, weight=_weight_callback(graph, events), heuristic=heuristic
        )
        observations.append((result, events))
    assert observations[0] == observations[1]
    assert observations[0][0] == ("raise", "NetworkXUnbounded", "Negative cycle detected.")
    if heuristic:
        assert observations[0][1] == [(0, 1), (1, 0)]
    else:
        assert len(observations[0][1]) == 2 * size - 1


@pytest.mark.parametrize("graph_type", GRAPH_TYPES)
@pytest.mark.parametrize("heuristic", [False, True])
@pytest.mark.parametrize("target", [None, 0, 1, 9, "missing", []])
def test_target_does_not_truncate_predecessor_or_distance_maps(graph_type, heuristic, target):
    observations = []
    for module in (fnx, nx):
        graph = getattr(module, graph_type)()
        graph.add_weighted_edges_from([(0, 1, 2), (1, 2, 1), (0, 2, 5), (2, 3, 4)])
        graph.add_node(9)
        if graph.is_multigraph():
            graph.add_edge(0, 1, weight=6)
        pred, dist = module.bellman_ford_predecessor_and_distance(
            graph, 0, target=target, heuristic=heuristic
        )
        assert set(pred) == set(dist) == {0, 1, 2, 3}
        assert dist[3] == 7
        observations.append(_ordered_typed((pred, dist)))
    assert observations[0] == observations[1]


@pytest.mark.parametrize("graph_type", GRAPH_TYPES)
@pytest.mark.parametrize("heuristic", [False, True])
@pytest.mark.parametrize("target", [0, 1, "missing"])
def test_target_does_not_hide_a_later_negative_cycle(graph_type, heuristic, target):
    observations = []
    for module in (fnx, nx):
        graph = getattr(module, graph_type)()
        graph.add_weighted_edges_from([(0, 1, 1), (1, 2, 1), (2, 3, -2)])
        if graph.is_directed():
            graph.add_edge(3, 2, weight=1)
        observations.append(_outcome(module, graph, target=target, heuristic=heuristic))
    assert observations[0] == observations[1] == (
        "raise", "NetworkXUnbounded", "Negative cycle detected."
    )


@pytest.mark.parametrize("graph_type", GRAPH_TYPES)
@pytest.mark.parametrize("heuristic", [False, True])
@pytest.mark.parametrize("self_loop", [False, True])
def test_disconnected_cycle_and_selfloop_contract(graph_type, heuristic, self_loop):
    observations = []
    for module in (fnx, nx):
        graph = getattr(module, graph_type)()
        graph.add_edge(0, 1, weight=2)
        if self_loop:
            graph.add_edge(10, 10, weight=-1)
        else:
            graph.add_edge(10, 11, weight=-1)
            if graph.is_directed():
                graph.add_edge(11, 10, weight=0)
        observations.append(_outcome(module, graph, target=10, heuristic=heuristic))
    assert observations[0] == observations[1]
    # NetworkX checks every self-loop before source relaxation, but an
    # unreachable longer negative cycle must not affect this source's result.
    assert observations[0][0] == ("raise" if self_loop else "return")


@pytest.mark.parametrize("graph_type", GRAPH_TYPES)
@pytest.mark.parametrize("heuristic", [False, True])
@pytest.mark.parametrize("mode", ["int", "huge_int", "fraction", "decimal"])
@pytest.mark.parametrize("seed", range(6))
def test_exact_numeric_maps_and_predecessor_order(graph_type, heuristic, mode, seed):
    rng = random.Random(seed)
    nodes = list(range(8))
    rng.shuffle(nodes)
    edges = []
    directed = "Di" in graph_type
    multi = "Multi" in graph_type
    for u in range(8):
        for v in range(u + 1, 8):
            if rng.random() >= 0.35:
                continue
            for _ in range(rng.randrange(1, 4) if multi else 1):
                value = rng.randrange(-3 if directed else 0, 6)
                if mode == "huge_int":
                    value *= 10**400
                elif mode == "fraction":
                    value = Fraction(value, 7)
                elif mode == "decimal":
                    value = Decimal(value) / 8
                edges.append((u, v, value))
    rng.shuffle(edges)
    observations = []
    for module in (fnx, nx):
        graph = getattr(module, graph_type)()
        graph.add_nodes_from(nodes)
        graph.add_weighted_edges_from(edges, weight="cost")
        observations.append(_outcome(module, graph, weight="cost", heuristic=heuristic))
    assert observations[0] == observations[1]
    assert observations[0][0] == "return"


@pytest.mark.parametrize("graph_type", GRAPH_TYPES)
@pytest.mark.parametrize("heuristic", [False, True])
@pytest.mark.parametrize("weight", [None, 17, ("edge", "cost")])
def test_nonstring_weight_keys_preserve_exact_arithmetic(graph_type, heuristic, weight):
    observations = []
    for module in (fnx, nx):
        graph = getattr(module, graph_type)()
        graph.add_edges_from([(0, 1), (1, 2), (0, 2)])
        for u, v, data in graph.edges(data=True):
            data[weight] = Fraction(5 if (u, v) == (0, 2) else 1, 3)
        observations.append(_outcome(module, graph, weight=weight, heuristic=heuristic))
    assert observations[0] == observations[1]


@pytest.mark.parametrize("graph_type", ["Graph", "DiGraph"])
def test_default_simple_graph_keeps_its_count_only_snapshot(monkeypatch, graph_type):
    graph = getattr(fnx, graph_type)()
    graph.add_weighted_edges_from([(0, 1, 2), (1, 2, 3)])
    namespace = fnx.bellman_ford_predecessor_and_distance.__globals__
    snapshot = namespace["_bellman_ford_pred_dist_inprocess"]
    calls = []

    def record_snapshot(*args, **kwargs):
        calls.append(True)
        return snapshot(*args, **kwargs)

    def unexpected_live_route(*args, **kwargs):
        raise AssertionError("ordinary default query discarded its snapshot route")

    monkeypatch.setitem(namespace, "_bellman_ford_pred_dist_inprocess", record_snapshot)
    monkeypatch.setitem(namespace, "_bellman_ford_predecessor_and_distance_inproc", unexpected_live_route)
    assert fnx.bellman_ford_predecessor_and_distance(graph, 0)[1] == {0: 0, 1: 2, 2: 5}
    assert calls == [True]


@pytest.mark.parametrize("graph_type", GRAPH_TYPES)
@pytest.mark.parametrize("heuristic", [False, True])
def test_private_rows_and_subclasses_reach_the_live_solver(monkeypatch, graph_type, heuristic):
    namespace = fnx.bellman_ford_predecessor_and_distance.__globals__
    owned = namespace["_bellman_ford_predecessor_and_distance_inproc"]
    calls = []

    def record_live(graph, *args, **kwargs):
        calls.append(graph)
        return owned(graph, *args, **kwargs)

    def unexpected_snapshot(*args, **kwargs):
        raise AssertionError("logical rows were replaced by a bulk snapshot")

    monkeypatch.setitem(namespace, "_bellman_ford_predecessor_and_distance_inproc", record_live)
    monkeypatch.setitem(namespace, "_bellman_ford_pred_dist_inprocess", unexpected_snapshot)
    for subclass in (False, True):
        observations = []
        actual = None
        for module in (fnx, nx):
            base = getattr(module, graph_type)
            graph_class = type("GraphSubclass", (base,), {}) if subclass else base
            graph = graph_class()
            graph.add_nodes_from(range(4))
            graph.add_edges_from([(0, 1), (1, 3)])
            first, second = {"weight": Fraction(2, 3)}, {"weight": Fraction(4, 3)}
            edge = {0: first} if graph.is_multigraph() else first
            other = {0: second} if graph.is_multigraph() else second
            rows = {0: {2: edge}, 1: {}, 2: {3: other}, 3: {}}
            if graph.is_directed():
                graph._succ = rows
                graph._pred = {0: {}, 1: {}, 2: {0: edge}, 3: {2: other}}
            else:
                rows[2][0] = edge
                rows[3][2] = other
            graph._adj = rows
            result = module.bellman_ford_predecessor_and_distance(
                graph, 0, target=3, heuristic=heuristic
            )
            assert result[1] == {0: 0, 2: Fraction(2, 3), 3: Fraction(2)}
            observations.append(_ordered_typed(result))
            if module is fnx:
                actual = graph
        assert observations[0] == observations[1]
        assert calls[-1] is actual


@pytest.mark.parametrize("graph_type", GRAPH_TYPES)
@pytest.mark.parametrize("heuristic", [False, True])
def test_weight_callbacks_keep_live_updates_and_order(graph_type, heuristic):
    def run(module):
        graph = getattr(module, graph_type)()
        graph.add_weighted_edges_from([(0, 1, 10), (0, 2, 1), (2, 1, 1), (1, 3, 10)])
        events = []

        def weight(u, v, data):
            events.append((u, v))
            if (u, v) == (0, 2):
                attrs = graph[1][3][0] if graph.is_multigraph() else graph[1][3]
                attrs["weight"] = 0
            if graph.is_multigraph():
                return min(attrs["weight"] for attrs in data.values())
            return data["weight"]

        result = module.bellman_ford_predecessor_and_distance(
            graph, 0, target=1, weight=weight, heuristic=heuristic
        )
        return _ordered_typed(result), events

    assert run(fnx) == run(nx)


@pytest.mark.parametrize("graph_type", GRAPH_TYPES)
@pytest.mark.parametrize("mode", ["true", "false", "raise"])
@pytest.mark.parametrize("shape", ["missing_source", "isolated_source", "edge"])
def test_custom_heuristic_truth_is_evaluated_at_relaxation(graph_type, mode, shape):
    def run(module):
        graph = getattr(module, graph_type)()
        graph.add_node(0)
        if shape == "edge":
            graph.add_edge(0, 1, weight=2)
        events = []

        class Heuristic:
            def __bool__(self):
                events.append("heuristic")
                if mode == "raise":
                    raise RuntimeError("heuristic evaluation")
                return mode == "true"

        result = _outcome(
            module, graph, source="missing" if shape == "missing_source" else 0,
            weight=_weight_callback(graph, events), heuristic=Heuristic(),
        )
        return result, events

    assert run(fnx) == run(nx)


@pytest.mark.parametrize("graph_type", GRAPH_TYPES)
@pytest.mark.parametrize("heuristic", [False, True])
@pytest.mark.parametrize("target", [None, 1, []])
@pytest.mark.parametrize("weight", ["cost", None])
def test_backend_predecessor_maps_keep_exact_costs_and_full_targets(
    graph_type, heuristic, target, weight
):
    graph = getattr(nx, graph_type)([(0, 1), (1, 2), (0, 2)])
    for u, v, data in graph.edges(data=True):
        data[weight] = Fraction(5 if (u, v) == (0, 2) else 1, 3)
    options = {"target": target, "weight": weight, "heuristic": heuristic}
    expected = nx.bellman_ford_predecessor_and_distance(
        graph, 0, backend="networkx", **options
    )
    actual = nx.bellman_ford_predecessor_and_distance(
        graph, 0, backend="franken_networkx", **options
    )
    assert _ordered_typed(actual) == _ordered_typed(expected)
    assert actual[1][2] == Fraction(2, 3)


@pytest.mark.parametrize("graph_type", GRAPH_TYPES)
@pytest.mark.parametrize("heuristic", [False, True])
@pytest.mark.parametrize("cached", [False, True])
@pytest.mark.parametrize("automatic", [False, True])
def test_backend_predecessor_weight_callbacks_keep_original_rows(
    graph_type, heuristic, cached, automatic, monkeypatch
):
    def run(backend):
        graph = getattr(nx, graph_type)()
        graph.add_weighted_edges_from([(0, 1, 10), (0, 2, 1), (2, 1, 1), (1, 3, 10)])
        if cached and backend == "franken_networkx":
            monkeypatch.setattr(nx.config, "cache_converted_graphs", True)
            nx.relabel_nodes(graph, {}, backend="franken_networkx")
            assert graph.__networkx_cache__["backends"]["franken_networkx"]
        events = []

        def weight(u, v, attrs):
            assert attrs is graph._adj[u][v]
            events.append((u, v))
            if (u, v) == (0, 2):
                later = graph[1][3][0] if graph.is_multigraph() else graph[1][3]
                later["weight"] = 0
            if graph.is_multigraph():
                return min(data["weight"] for data in attrs.values())
            return attrs["weight"]

        kwargs = {"backend": backend}
        if automatic and backend == "franken_networkx":
            monkeypatch.setattr(nx.config.backend_priority, "algos", [backend])
            kwargs = {}
        result = nx.bellman_ford_predecessor_and_distance(
            graph, 0, 1, weight, heuristic, **kwargs
        )
        if backend == "franken_networkx":
            assert not graph.__networkx_cache__.get("backends")
        return _ordered_typed(result), events

    expected = run("networkx")
    assert run("franken_networkx") == expected


@pytest.mark.parametrize("name", ["goldberg_radzik", "bellman_ford_predecessor_and_distance"])
@pytest.mark.parametrize("graph_type", GRAPH_TYPES)
@pytest.mark.parametrize("route", ["native", "foreign", "backend"])
@pytest.mark.parametrize("source", [0, "missing"])
def test_predecessor_public_source_validation_keeps_membership_reads(
    name, graph_type, route, source
):
    def run(reference):
        events = []
        module = fnx if not reference and route == "native" else nx
        base = getattr(module, graph_type)

        class ObservedGraph(base):
            def __contains__(self, node):
                events.append(("contains", node))
                return super().__contains__(node)

        graph = ObservedGraph([(0, 1)])
        if module is fnx:
            # Use logical rows to isolate algorithm source validation from
            # membership checks made by native adjacency view construction.
            edge = {0: {}} if graph.is_multigraph() else {}
            rows = {0: {1: edge}, 1: {}}
            if graph.is_directed():
                graph._succ = rows
                graph._pred = {0: {}, 1: {0: edge}}
            else:
                rows[1][0] = edge
            graph._adj = rows
        events.clear()
        if reference:
            function, kwargs = getattr(nx, name), {"backend": "networkx"}
        elif route == "backend":
            function, kwargs = getattr(nx, name), {"backend": "franken_networkx"}
        else:
            function, kwargs = getattr(fnx, name), {}
        try:
            result = "return", _ordered_typed(function(graph, source, **kwargs))
        except Exception as error:
            result = "raise", type(error).__name__, str(error)
        return result, events

    expected, actual = run(True), run(False)
    assert actual == expected
    assert actual[1][0] == ("contains", source)
    if source == "missing":
        assert actual[0] == (
            "raise", "NodeNotFound", "Node missing is not found in the graph"
        )
        assert actual[1] == [("contains", source)]
