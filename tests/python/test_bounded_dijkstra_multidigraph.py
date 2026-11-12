"""Local point/cutoff queries and distance-only single-source fallbacks."""

from decimal import Decimal
from fractions import Fraction
import math
import random

import networkx as nx
import pytest

import franken_networkx as fnx


BOUNDED_QUERIES = [
    ("dijkstra_path", {"target": 3}),
    ("dijkstra_path_length", {"target": 3}),
    ("single_source_dijkstra", {"target": 3}),
    ("single_source_dijkstra", {"target": 3, "cutoff": 128}),
    ("single_source_dijkstra", {"cutoff": 3}),
    ("single_source_dijkstra_path", {"cutoff": 3}),
    ("single_source_dijkstra_path_length", {"cutoff": 3}),
]


def _ordered_typed(value):
    if isinstance(value, dict):
        return [(key, _ordered_typed(item)) for key, item in value.items()]
    if isinstance(value, (list, tuple)):
        return type(value).__name__, [_ordered_typed(item) for item in value]
    return type(value).__name__, repr(value)


def _outcome(query, graph, source, **kwargs):
    try:
        return "return", _ordered_typed(query(graph, source, **kwargs))
    except Exception as exc:
        return "raise", type(exc).__name__, str(exc)


def _chain_pair(mode="int", size=256, graph_type="MultiDiGraph"):
    actual, expected = getattr(fnx, graph_type)(), getattr(nx, graph_type)()
    for graph in (actual, expected):
        for node in range(size):
            value = 1
            if mode == "float" or (mode == "mixed" and node % 2):
                value = 1.0
            elif mode == "fraction":
                value = Fraction(3, 2)
            elif mode == "decimal":
                value = Decimal("1.5")
            elif mode == "negative":
                value = -1
            graph.add_edge(node, node + 1, weight=value)
            if graph.is_multigraph():
                graph.add_edge(node, node + 1, weight=5)
    return actual, expected


@pytest.mark.parametrize("name,options", BOUNDED_QUERIES)
@pytest.mark.parametrize("mode", ["int", "float", "mixed"])
def test_bounded_queries_do_no_global_preparation(monkeypatch, name, options, mode):
    actual, expected = _chain_pair(mode)
    want = getattr(nx, name)(expected, 0, **options)
    namespace = getattr(fnx, name).__globals__
    owned = namespace["_dijkstra_multisource_inproc"]
    calls = []

    def record_search(*args, **kwargs):
        result = owned(*args, **kwargs)
        if name.endswith("path_length"):
            assert kwargs.get("paths") is None
        elif "target" in options:
            # A target+cutoff query must not build paths to every node inside
            # the cutoff merely to select the target afterward.
            assert list(kwargs["paths"]) == [0, 3]
        calls.append((kwargs, list(result)))
        return result

    def global_preparation(*args, **kwargs):
        raise AssertionError("bounded query prepared unrelated rows or native paths")

    monkeypatch.setitem(namespace, "_dijkstra_multisource_inproc", record_search)
    for helper in (
        "_coerce_arg_to_fnx_graph", "_should_delegate_dijkstra_to_networkx",
        "_sp_weights_need_networkx_for_type_parity", "_dijkstra_weight_route",
        "_raw_multidigraph_dijkstra_path_target",
        "_raw_multidigraph_dijkstra_path_length_target",
        "_raw_mdg_ss_dijkstra", "_raw_mdg_ss_dijkstra_path_length",
        "_multigraph_collapse_min_weight",
    ):
        monkeypatch.setitem(namespace, helper, global_preparation)
    got = getattr(fnx, name)(actual, 0, **options)
    assert _ordered_typed(got) == _ordered_typed(want)
    assert len(calls) == 1
    assert calls[0][1] == [0, 1, 2, 3]
    for key, value in options.items():
        assert calls[0][0][key] == value


@pytest.mark.parametrize("name", [
    "single_source_dijkstra", "single_source_dijkstra_path",
    "single_source_dijkstra_path_length",
])
@pytest.mark.parametrize("cutoff", [None, math.inf, math.nan])
@pytest.mark.parametrize("mode", ["int", "float", "mixed"])
def test_unbounded_single_source_queries_retain_native(monkeypatch, name, cutoff, mode):
    actual, expected = _chain_pair(mode, size=16)
    want = getattr(nx, name)(expected, 0, cutoff=cutoff)
    namespace = getattr(fnx, name).__globals__
    native_name = (
        "_raw_mdg_ss_dijkstra_path_length"
        if name.endswith("path_length") else "_raw_mdg_ss_dijkstra"
    )
    native = namespace[native_name]
    calls = []

    def record_native(*args, **kwargs):
        calls.append(kwargs)
        return native(*args, **kwargs)

    def left_native(*args, **kwargs):
        raise AssertionError("unbounded ordinary single-source query left native")

    monkeypatch.setitem(namespace, native_name, record_native)
    monkeypatch.setitem(namespace, "_multi_source_dijkstra_inproc", left_native)
    monkeypatch.setitem(namespace, "_dijkstra_multisource_inproc", left_native)
    assert _ordered_typed(getattr(fnx, name)(actual, 0, cutoff=cutoff)) == _ordered_typed(want)
    assert len(calls) == 1
    assert calls[0]["cutoff"] is cutoff


@pytest.mark.parametrize("graph_type", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("mode", ["fraction", "decimal"])
def test_exact_length_fallback_never_allocates_paths(monkeypatch, graph_type, mode):
    actual, expected = _chain_pair(mode, size=192, graph_type=graph_type)
    want = nx.single_source_dijkstra_path_length(expected, 0)
    namespace = fnx.single_source_dijkstra_path_length.__globals__
    owned = namespace["_dijkstra_multisource_inproc"]
    calls = []

    def paths_requested(*args, **kwargs):
        raise AssertionError("length fallback allocated source-wide path output")

    def distance_only(*args, **kwargs):
        assert kwargs.get("paths") is None
        calls.append(True)
        return owned(*args, **kwargs)

    monkeypatch.setitem(namespace, "_multi_source_dijkstra_inproc", paths_requested)
    monkeypatch.setitem(namespace, "_dijkstra_multisource_inproc", distance_only)
    got = fnx.single_source_dijkstra_path_length(actual, 0)
    assert _ordered_typed(got) == _ordered_typed(want)
    assert calls == [True]


def test_declined_native_length_query_stays_distance_only(monkeypatch):
    actual, expected = _chain_pair("negative", size=192)
    want = nx.single_source_dijkstra_path_length(expected, 0)
    namespace = fnx.single_source_dijkstra_path_length.__globals__
    native = namespace["_raw_mdg_ss_dijkstra_path_length"]
    declines = []

    def record_native(*args, **kwargs):
        result = native(*args, **kwargs)
        declines.append(result is None)
        return result

    def paths_requested(*args, **kwargs):
        raise AssertionError("declined native length query allocated path output")

    monkeypatch.setitem(namespace, "_raw_mdg_ss_dijkstra_path_length", record_native)
    monkeypatch.setitem(namespace, "_multi_source_dijkstra_inproc", paths_requested)
    assert _ordered_typed(fnx.single_source_dijkstra_path_length(actual, 0)) == _ordered_typed(want)
    assert declines == [True]


@pytest.mark.parametrize("name", ["dijkstra_path", "dijkstra_path_length", "single_source_dijkstra"])
@pytest.mark.parametrize("source", [0, "missing", []])
@pytest.mark.parametrize("target", [0, 2, "missing", None, []])
@pytest.mark.parametrize("cost", [1, "invalid"])
def test_endpoint_and_reachable_error_order_matches_networkx(name, source, target, cost):
    actual, expected = fnx.MultiDiGraph(), nx.MultiDiGraph()
    for graph in (actual, expected):
        graph.add_edge(0, 1, weight=cost)
        graph.add_node(2)
    assert _outcome(getattr(fnx, name), actual, source, target=target) == _outcome(
        getattr(nx, name), expected, source, target=target
    )


@pytest.mark.parametrize("name,options", [
    ("dijkstra_path", {}),
    ("single_source_dijkstra", {}),
    ("single_source_dijkstra", {"cutoff": 128}),
])
@pytest.mark.parametrize("same_endpoint", [False, True])
def test_point_paths_retain_supplied_endpoint_aliases(name, options, same_endpoint):
    class NodeAlias(int):
        pass

    actual, expected = _chain_pair(size=4)
    source = NodeAlias(0)
    target = NodeAlias(0 if same_endpoint else 3)
    for module, graph in ((fnx, actual), (nx, expected)):
        result = getattr(module, name)(graph, source, target=target, **options)
        path = result if name == "dijkstra_path" else result[1]
        assert path[0] is (target if same_endpoint else source)
        assert path[-1] is target


@pytest.mark.parametrize("graph_type", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("source", ["missing", []])
def test_exact_length_fallback_validates_source_before_traversal(monkeypatch, graph_type, source):
    actual, expected = _chain_pair("fraction", size=3, graph_type=graph_type)
    namespace = fnx.single_source_dijkstra_path_length.__globals__

    def invalid_source_was_traversed(*args, **kwargs):
        raise AssertionError("distance-only fallback traversed an invalid source")

    monkeypatch.setitem(namespace, "_dijkstra_multisource_inproc", invalid_source_was_traversed)
    assert _outcome(fnx.single_source_dijkstra_path_length, actual, source) == _outcome(
        nx.single_source_dijkstra_path_length, expected, source
    )


@pytest.mark.parametrize("name,options", BOUNDED_QUERIES)
@pytest.mark.parametrize("bad_edge", [(1, 2), (3, 4), (99, 100)])
def test_invalid_weights_are_read_only_when_reached(name, options, bad_edge):
    actual, expected = _chain_pair(size=8)
    for graph in (actual, expected):
        graph.add_edge(99, 100, weight=1)
        graph[bad_edge[0]][bad_edge[1]][0]["weight"] = "invalid"
    assert _outcome(getattr(fnx, name), actual, 0, **options) == _outcome(
        getattr(nx, name), expected, 0, **options
    )


@pytest.mark.parametrize("name,options", BOUNDED_QUERIES)
def test_callbacks_keep_live_parallel_rows(name, options):
    def run(module):
        graph = module.MultiDiGraph()
        graph.add_weighted_edges_from([(0, 1, 10), (0, 2, 1), (2, 1, 1), (1, 3, 10)])
        graph.add_edge(1, 3, weight=30)
        events = []

        def weight(u, v, data):
            events.append((u, v))
            if (u, v) == (0, 2):
                graph[1][3][0]["weight"] = 0
            if (u, v) == (0, 1):
                return None
            return min(attrs.get("weight", 1) for attrs in data.values())

        result = getattr(module, name)(graph, 0, weight=weight, **options)
        return _ordered_typed(result), events

    assert run(fnx) == run(nx)


@pytest.mark.parametrize("name", [
    "single_source_dijkstra", "single_source_dijkstra_path",
    "single_source_dijkstra_path_length",
])
@pytest.mark.parametrize("cutoff", [
    Decimal("0.999999999999999999999999999"),
    Fraction((1 << 60) - 1, 1 << 60), -math.inf,
])
def test_cutoff_boundaries_keep_exact_comparisons(name, cutoff):
    actual, expected = _chain_pair(size=3)
    assert _outcome(getattr(fnx, name), actual, 0, cutoff=cutoff) == _outcome(
        getattr(nx, name), expected, 0, cutoff=cutoff
    )


@pytest.mark.parametrize("seed", range(6))
@pytest.mark.parametrize("mode", ["int", "float", "mixed", "fraction", "decimal"])
def test_random_parallel_routes_match_order_types_and_ties(seed, mode):
    rng = random.Random(seed)
    nodes = [(i, "node") for i in range(12)] if seed % 2 else list(range(12))
    rng.shuffle(nodes)
    actual, expected = fnx.MultiDiGraph(), nx.MultiDiGraph()
    for graph in (actual, expected):
        graph.add_nodes_from(nodes)
    for u in nodes:
        for v in nodes:
            if rng.random() >= 0.18:
                continue
            for key in range(rng.randrange(1, 4)):
                cost = rng.choice([0, 1, 2, 5])
                if mode == "float" or (mode == "mixed" and rng.random() < 0.5):
                    cost = float(cost)
                elif mode == "fraction":
                    cost = Fraction(cost, 2)
                elif mode == "decimal":
                    cost = Decimal(cost) / 2
                attrs = {} if rng.random() < 0.15 else {"weight": cost}
                for graph in (actual, expected):
                    graph.add_edge(u, v, key=key, **attrs)
    source = nodes[0]
    for target in (nodes[-1], source, "missing"):
        for name in ("dijkstra_path", "dijkstra_path_length", "single_source_dijkstra"):
            assert _outcome(getattr(fnx, name), actual, source, target=target) == _outcome(
                getattr(nx, name), expected, source, target=target
            )
        assert _outcome(fnx.single_source_dijkstra, actual, source, target=target, cutoff=3) == _outcome(
            nx.single_source_dijkstra, expected, source, target=target, cutoff=3
        )
    for cutoff in (-1, 0, 3.5):
        for name in (
            "single_source_dijkstra", "single_source_dijkstra_path",
            "single_source_dijkstra_path_length",
        ):
            assert _outcome(getattr(fnx, name), actual, source, cutoff=cutoff) == _outcome(
                getattr(nx, name), expected, source, cutoff=cutoff
            )
