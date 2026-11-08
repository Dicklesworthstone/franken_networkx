"""Bounded multi-source routing and distance-only searches on parallel arcs."""

from decimal import Decimal
from fractions import Fraction
import math
import random

import networkx as nx
import pytest

import franken_networkx as fnx


def _ordered_typed(value):
    if isinstance(value, dict):
        return [(key, _ordered_typed(item)) for key, item in value.items()]
    if isinstance(value, (list, tuple)):
        return type(value).__name__, [_ordered_typed(item) for item in value]
    return type(value).__name__, repr(value)


def _outcome(query, graph, sources, **kwargs):
    try:
        return "return", _ordered_typed(query(graph, sources, **kwargs))
    except Exception as exc:
        return "raise", type(exc).__name__, str(exc)


def _random_parallel_graphs(seed, mode):
    rng = random.Random(seed)
    nodes = [(i, "node") for i in range(20)] if seed % 2 else list(range(20))
    rng.shuffle(nodes)
    actual, expected = fnx.MultiDiGraph(), nx.MultiDiGraph()
    for graph in (actual, expected):
        graph.add_nodes_from(nodes)
    for u in nodes:
        for v in nodes:
            if rng.random() >= 0.13:
                continue
            for key in range(rng.randrange(1, 4)):
                value = rng.choice([0, 1, 2, 5])
                if mode == "float" or (mode == "mixed" and rng.random() < 0.5):
                    value = float(value)
                attrs = {} if rng.random() < 0.15 else {"cost": value}
                for graph in (actual, expected):
                    graph.add_edge(u, v, key=key, **attrs)
    return actual, expected, nodes


@pytest.mark.parametrize("seed", range(8))
@pytest.mark.parametrize("mode", ["int", "float", "mixed"])
@pytest.mark.parametrize("cutoff", [None, -1, 0, 3.5, math.nan, math.inf])
def test_directed_parallel_routes_match_networkx_order_and_types(seed, mode, cutoff):
    actual, expected, nodes = _random_parallel_graphs(seed, mode)
    sources = nodes[:2]
    options = {"cutoff": cutoff, "weight": "cost"}
    for target in (None, nodes[-1], sources[0], "missing"):
        assert _outcome(
            fnx.multi_source_dijkstra, actual, sources, target=target, **options
        ) == _outcome(
            nx.multi_source_dijkstra, expected, sources, target=target, **options
        )
    for name in ("multi_source_dijkstra_path", "multi_source_dijkstra_path_length"):
        assert _outcome(getattr(fnx, name), actual, sources, **options) == _outcome(
            getattr(nx, name), expected, sources, **options
        )


@pytest.mark.parametrize("mode", ["int", "float", "mixed"])
@pytest.mark.parametrize("bound", ["cutoff", "target"])
def test_native_search_receives_the_bound_and_does_not_settle_the_tail(monkeypatch, mode, bound):
    actual, expected = fnx.MultiDiGraph(), nx.MultiDiGraph()
    for graph in (actual, expected):
        graph.add_node(1000)
        for node in range(256):
            value = 1.0 if mode == "float" or (mode == "mixed" and node % 2) else 1
            graph.add_edge(node, node + 1, weight=value)
            graph.add_edge(node, node + 1, weight=5)
    sources = [0, 1000]
    options = {"cutoff": 2.5} if bound == "cutoff" else {"target": 2}
    want = nx.multi_source_dijkstra(expected, sources, **options)
    namespace = fnx.multi_source_dijkstra.__globals__
    native = namespace["_raw_multi_source_dijkstra"]
    calls = []

    def record_native(*args, **kwargs):
        result = native(*args, **kwargs)
        calls.append((kwargs, list(result[0])))
        return result

    def unexpected_fallback(*args, **kwargs):
        raise AssertionError("ordinary parallel arcs left the bounded native route")

    monkeypatch.setitem(namespace, "_raw_multi_source_dijkstra", record_native)
    monkeypatch.setitem(namespace, "_multi_source_dijkstra_inproc", unexpected_fallback)
    monkeypatch.setitem(namespace, "_reorder_by_distance", unexpected_fallback)
    assert _ordered_typed(fnx.multi_source_dijkstra(actual, sources, **options)) == _ordered_typed(want)
    assert len(calls) == 1
    assert calls[0][0][bound] == options[bound]
    assert calls[0][1] == [0, 1000, 1, 2]


@pytest.mark.parametrize("graph_type", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("mode", ["native", "decimal", "callable"])
def test_distance_only_queries_never_build_path_dictionaries(monkeypatch, graph_type, mode):
    actual, expected = getattr(fnx, graph_type)(), getattr(nx, graph_type)()
    for graph in (actual, expected):
        for node in range(128):
            value = Decimal("1.25") if mode == "decimal" else 1
            graph.add_edge(node, node + 1, weight=value)
            if graph.is_multigraph():
                graph.add_edge(node, node + 1, weight=10)

    def weight(u, v, attrs):
        if actual.is_multigraph():
            return min(data["weight"] for data in attrs.values())
        return attrs["weight"]

    options = {"weight": weight} if mode == "callable" else {}
    sources = [0, 64]
    want = nx.multi_source_dijkstra_path_length(expected, sources, **options)
    namespace = fnx.multi_source_dijkstra_path_length.__globals__
    owned = namespace["_dijkstra_multisource_inproc"]

    def paths_were_requested(*args, **kwargs):
        raise AssertionError("distance-only query allocated a path dictionary")

    def distance_only_owned(*args, **kwargs):
        assert kwargs.get("paths") is None
        return owned(*args, **kwargs)

    monkeypatch.setitem(namespace, "multi_source_dijkstra", paths_were_requested)
    monkeypatch.setitem(namespace, "_raw_multi_source_dijkstra", paths_were_requested)
    monkeypatch.setitem(namespace, "_multi_source_dijkstra_inproc", paths_were_requested)
    monkeypatch.setitem(namespace, "_dijkstra_multisource_inproc", distance_only_owned)
    actual_result = fnx.multi_source_dijkstra_path_length(actual, sources, **options)
    assert _ordered_typed(actual_result) == _ordered_typed(want)


@pytest.mark.parametrize("name", ["multi_source_dijkstra", "multi_source_dijkstra_path", "multi_source_dijkstra_path_length"])
def test_weight_callbacks_keep_live_parallel_rows(name):
    def run(module):
        graph = module.MultiDiGraph()
        graph.add_weighted_edges_from([(0, 1, 10), (0, 2, 1), (2, 1, 1), (1, 3, 10), (2, 3, 20)])
        graph.add_edge(1, 3, weight=30)
        graph.add_node(4)
        events = []

        def weight(u, v, data):
            events.append((u, v))
            if (u, v) == (0, 2):
                graph[1][3][0]["weight"] = 0
            if (u, v) == (0, 1):
                return None
            return min(attrs.get("weight", 1) for attrs in data.values())

        result = getattr(module, name)(graph, [0, 4], weight=weight)
        return _ordered_typed(result), events

    assert run(fnx) == run(nx)


@pytest.mark.parametrize("name", ["multi_source_dijkstra", "multi_source_dijkstra_path_length"])
@pytest.mark.parametrize("cutoff", [Decimal("0.999999999999999999999999999"), Fraction((1 << 60) - 1, 1 << 60)])
def test_exact_cutoffs_still_use_python_comparisons(monkeypatch, name, cutoff):
    actual, expected = fnx.MultiDiGraph(), nx.MultiDiGraph()
    for graph in (actual, expected):
        graph.add_edge(0, 1, weight=1)
        graph.add_edge(0, 1, weight=2)
    namespace = getattr(fnx, name).__globals__

    def float_cutoff_was_requested(*args, **kwargs):
        raise AssertionError("an exact cutoff was sent through an f64 binding")

    monkeypatch.setitem(namespace, "_raw_multi_source_dijkstra", float_cutoff_was_requested)
    monkeypatch.setattr(namespace["_fnx"], "multi_source_dijkstra_path_length", float_cutoff_was_requested)
    assert _outcome(getattr(fnx, name), actual, [0], cutoff=cutoff) == _outcome(
        getattr(nx, name), expected, [0], cutoff=cutoff
    )


def test_parallel_weight_changes_invalidate_native_queries():
    actual, expected = fnx.MultiDiGraph(), nx.MultiDiGraph()
    for graph in (actual, expected):
        graph.add_edge(0, 1, key="slow", weight=5)
        graph.add_edge(0, 1, key="fast", weight=1.0)
        graph.add_edge(1, 2, weight=2)
        graph.add_edge(0, 2, weight=10)
    held_actual, held_expected = actual[0][1]["fast"], expected[0][1]["fast"]
    for value in (1.0, 20, 0.5):
        held_actual["weight"] = held_expected["weight"] = value
        for name in ("multi_source_dijkstra", "multi_source_dijkstra_path_length"):
            assert _outcome(getattr(fnx, name), actual, [0], cutoff=6) == _outcome(
                getattr(nx, name), expected, [0], cutoff=6
            )
