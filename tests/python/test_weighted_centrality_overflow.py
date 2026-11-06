"""Finite edge weights can overflow inside weighted centrality searches.

The native Brandes/Newman kernels must distinguish discovery from distance.
The owned Python Brandes helper must also retain equal predecessors after
settlement: infinite distances create those ties even with positive weights.
Compare with the live oracle, including its non-textbook undirected results.
"""

from decimal import Decimal
from fractions import Fraction

import networkx as nx
import pytest
from networkx.algorithms.centrality.betweenness import (
    _single_source_dijkstra_path_basic as nx_dijkstra_basic,
)

import franken_networkx as fnx


GRAPH_CLASSES = ("Graph", "DiGraph", "MultiGraph", "MultiDiGraph")
SCENARIOS = ("overflow", "finite_alternative")
NATIVE_HELPERS = (
    "_raw_betweenness_centrality",
    "_betweenness_centrality_sampled_rust",
    "_raw_edge_betweenness_centrality",
    "_betweenness_centrality_subset_weighted_rust",
    "_edge_betweenness_centrality_subset_weighted_rust",
    "_raw_load_centrality_weighted",
    "_raw_percolation_centrality_weighted",
)


@pytest.fixture(params=GRAPH_CLASSES)
def graph_class(request):
    return request.param


@pytest.fixture
def native_calls(monkeypatch):
    """Observe the actual native entrypoints without replacing their work."""
    calls = dict.fromkeys(NATIVE_HELPERS, 0)
    for name in NATIVE_HELPERS:
        original = getattr(fnx, name)

        def recording(*args, _name=name, _original=original, **kwargs):
            calls[_name] += 1
            return _original(*args, **kwargs)

        monkeypatch.setattr(fnx, name, recording)
    return calls


def _twins(graph_class, scenario):
    edges = [(0, 1, 1e308), (1, 2, 1e308), (2, 3, 1.0)]
    node_count = 5
    if scenario == "finite_alternative":
        # From source 0, vertex 2 is first queued at infinity via vertex 1,
        # then improved to a finite distance through vertex 4.
        edges += [(0, 4, 1.5e308), (4, 2, 1.0)]
        node_count = 6
    graphs = []
    for module in (nx, fnx):
        graph = getattr(module, graph_class)()
        graph.add_nodes_from(range(node_count))
        graph.add_weighted_edges_from(edges)
        if graph.is_multigraph():
            # The Python routes must split equal minimum edge contributions
            # between keys and leave the heavier parallel edge at zero.
            graph.add_edge(1, 2, key="equal", weight=1e308)
            graph.add_edge(1, 2, key="heavier", weight=1.5e308)
        graphs.append(graph)
    return graphs


def _compare(algorithm, graphs, native_calls, native_helper, **kwargs):
    reference, graph = graphs
    expected = getattr(nx, algorithm)(reference, backend="networkx", **kwargs)
    before = native_calls[native_helper]
    actual = getattr(fnx, algorithm)(graph, **kwargs)
    if isinstance(expected, dict):
        assert list(actual.items()) == list(expected.items()), (algorithm, kwargs)
    else:
        assert actual == expected, (algorithm, kwargs)
    if not graph.is_multigraph():
        assert native_calls[native_helper] == before + 1, (
            "finite weights must retain their native centrality route",
            algorithm,
            kwargs,
        )
    return actual


@pytest.mark.parametrize("endpoints", [False, True])
def test_node_betweenness_overflow(graph_class, endpoints, native_calls):
    for scenario in SCENARIOS:
        graphs = _twins(graph_class, scenario)
        isolated = len(graphs[0]) - 1
        for normalized in (False, True):
            for sample in ({}, {"k": 2, "seed": 2}):
                helper = (
                    "_betweenness_centrality_sampled_rust"
                    if sample
                    else "_raw_betweenness_centrality"
                )
                scores = _compare(
                    "betweenness_centrality", graphs, native_calls, helper,
                    weight="weight", normalized=normalized, endpoints=endpoints,
                    **sample,
                )
                assert scores[isolated] == 0.0


@pytest.mark.parametrize("normalized", [False, True])
def test_edge_betweenness_overflow(graph_class, normalized, native_calls):
    for scenario in SCENARIOS:
        graphs = _twins(graph_class, scenario)
        for sample in ({}, {"k": 2, "seed": 2}):
            scores = _compare(
                "edge_betweenness_centrality", graphs, native_calls,
                "_raw_edge_betweenness_centrality",
                weight="weight", normalized=normalized, **sample,
            )
            if graphs[0].is_multigraph():
                assert scores[1, 2, "heavier"] == 0.0


@pytest.mark.parametrize("edge_scores", [False, True], ids=["nodes", "edges"])
def test_subset_betweenness_overflow(graph_class, edge_scores, native_calls):
    if edge_scores:
        algorithm = "edge_betweenness_centrality_subset"
        helper = "_edge_betweenness_centrality_subset_weighted_rust"
    else:
        algorithm = "betweenness_centrality_subset"
        helper = "_betweenness_centrality_subset_weighted_rust"
    for scenario in SCENARIOS:
        graphs = _twins(graph_class, scenario)
        isolated = len(graphs[0]) - 1
        for normalized in (False, True):
            for targets in ([3], [isolated]):
                scores = _compare(
                    algorithm, graphs, native_calls, helper,
                    sources=[0], targets=targets, weight="weight",
                    normalized=normalized,
                )
                if targets == [isolated]:
                    assert all(score == 0.0 for score in scores.values())


def test_weighted_load_overflow(graph_class, native_calls):
    for scenario in SCENARIOS:
        graphs = _twins(graph_class, scenario)
        for normalized in (False, True):
            scores = _compare(
                "load_centrality", graphs, native_calls,
                "_raw_load_centrality_weighted",
                weight="weight", normalized=normalized,
            )
            assert scores[len(graphs[0]) - 1] == 0.0
            _compare(
                "load_centrality", graphs, native_calls,
                "_raw_load_centrality_weighted",
                v=2, weight="weight", normalized=normalized,
            )


def test_weighted_load_rereads_after_a_self_predecessor(graph_class, native_calls):
    # A self predecessor changes the load still to be divided among later
    # predecessors. Hoisting that division changes even finite-distance cases.
    for first_weight in (1e308, 1.0):
        graphs = []
        for module in (nx, fnx):
            graph = getattr(module, graph_class)()
            graph.add_nodes_from(range(6))
            graph.add_weighted_edges_from([
                (0, 1, first_weight), (1, 2, first_weight),
                (2, 3, 0.0), (3, 2, 0.0), (3, 4, 0.0), (2, 2, 0.0),
            ])
            graphs.append(graph)
        scores = _compare(
            "load_centrality", graphs, native_calls,
            "_raw_load_centrality_weighted",
            weight="weight", normalized=False,
        )
        assert scores[5] == 0.0
        if first_weight == 1e308:
            expected = (
                [0.0, 1.0, 5.0, 3.333333333333333, 0.0, 0.0]
                if graphs[0].is_directed()
                else [0.0, 3.6666666666666665, 6.666666666666666,
                      2.888888888888889, 2.0, 0.0]
            )
            assert list(scores.values()) == expected


def test_weighted_percolation_overflow(graph_class, native_calls):
    for scenario in SCENARIOS:
        graphs = _twins(graph_class, scenario)
        reference = graphs[0]
        for states in (
            dict.fromkeys(reference, 1.0),
            {node: (node + 1) / 8 for node in reference},
        ):
            scores = _compare(
                "percolation_centrality", graphs, native_calls,
                "_raw_percolation_centrality_weighted",
                weight="weight", states=states,
            )
            assert scores[len(reference) - 1] == 0.0


def test_owned_brandes_retains_finalized_infinite_predecessors(graph_class):
    for scenario in SCENARIOS:
        reference, graph = _twins(graph_class, scenario)
        expected = nx_dijkstra_basic(reference, 0, "weight")
        actual = fnx._single_source_dijkstra_path_basic_local(graph, 0, "weight")
        assert actual == expected
        if scenario == "overflow":
            assert actual[3][2] == actual[3][3] == float("inf")
            assert len(reference) - 1 not in actual[3]
            if not reference.is_directed():
                # Vertex 2 is already settled when vertex 3 supplies this
                # equally distant predecessor. It must not be discarded.
                assert 3 in actual[1][2]


WEIGHTED_CONSUMERS = (
    ("betweenness_centrality_subset", "_betweenness_centrality_subset_weighted_rust"),
    ("edge_betweenness_centrality_subset", "_edge_betweenness_centrality_subset_weighted_rust"),
    ("percolation_centrality", "_raw_percolation_centrality_weighted"),
    ("load_centrality", "_raw_load_centrality_weighted"),
)

EXACT_WEIGHT_CASES = (
    pytest.param((2**54, 1, 2), id="large_integer"),
    pytest.param((2**53 - 1, 4, 5), id="integer_sum"),
    pytest.param(
        (Fraction(1), Fraction(1, 2**55), Fraction(1, 2**54)),
        id="fraction",
    ),
    pytest.param(
        (Decimal(1), Decimal("1e-27"), Decimal("2e-27")),
        id="decimal",
    ),
)


def _exact_weight_twins(graph_class, weights):
    head, short_tail, long_tail = weights
    graphs = []
    for module in (nx, fnx):
        graph = getattr(module, graph_class)()
        graph.add_nodes_from(range(5))
        graph.add_weighted_edges_from([
            (0, 1, head), (1, 3, short_tail),
            (0, 2, head), (2, 3, long_tail),
        ])
        if graph.is_multigraph():
            graph.add_edge(0, 1, key="equal", weight=head)
        graphs.append(graph)
    return graphs


def _consumer_kwargs(algorithm):
    if "subset" in algorithm:
        return {"sources": [0], "targets": [3]}
    return {}


@pytest.mark.parametrize("weights", EXACT_WEIGHT_CASES)
def test_weighted_consumers_preserve_exact_path_costs(
    graph_class, weights, native_calls
):
    reference, native_graph = _exact_weight_twins(graph_class, weights)
    for algorithm, native_helper in WEIGHTED_CONSUMERS:
        for normalized in (False, True):
            kwargs = _consumer_kwargs(algorithm)
            if algorithm != "percolation_centrality":
                kwargs["normalized"] = normalized
            elif normalized:
                continue
            expected = getattr(nx, algorithm)(reference, weight="weight", **kwargs)
            for graph in (native_graph, reference):
                before = native_calls[native_helper]
                actual = getattr(fnx, algorithm)(graph, weight="weight", **kwargs)
                assert list(actual.items()) == list(expected.items())
                assert native_calls[native_helper] == before, (
                    "exact Python costs must not be rounded before path counting",
                    algorithm,
                )
                if algorithm == "load_centrality":
                    assert fnx.load_centrality(
                        graph, v=1, weight="weight", **kwargs
                    ) == expected[1]


@pytest.mark.parametrize("algorithm,native_helper", WEIGHTED_CONSUMERS)
def test_weighted_consumers_keep_ordinary_native_routes(
    graph_class, algorithm, native_helper, native_calls
):
    graphs = _exact_weight_twins(graph_class, (100, 1, 2))
    _compare(
        algorithm, graphs, native_calls, native_helper,
        weight="weight", **_consumer_kwargs(algorithm),
    )


def _callback_weight(graph):
    if graph.is_multigraph():
        return lambda u, v, data: min(attrs.get("weight", 1) for attrs in data.values())
    return lambda u, v, data: data.get("weight", 1)


@pytest.mark.parametrize("callable_weight", [False, True])
def test_weighted_consumers_none_weight_contract(graph_class, callable_weight):
    graphs = []
    for module in (nx, fnx):
        graph = getattr(module, graph_class)()
        graph.add_nodes_from(range(4))
        graph.add_weighted_edges_from([
            (0, 1, 1), (1, 2, None), (0, 2, 2), (2, 3, 1),
        ])
        graphs.append(graph)
    reference, graph = graphs
    for algorithm, _ in WEIGHTED_CONSUMERS:
        kwargs = _consumer_kwargs(algorithm)
        reference_weight = _callback_weight(reference) if callable_weight else "weight"
        actual_weight = _callback_weight(graph) if callable_weight else "weight"
        if algorithm == "load_centrality":
            # Newman load uses ordinary Dijkstra, where None hides an edge.
            expected = nx.load_centrality(reference, weight=reference_weight)
            assert fnx.load_centrality(graph, weight=actual_weight) == expected
        else:
            # Brandes counts paths using edge arithmetic; None is an error.
            with pytest.raises(TypeError) as expected:
                getattr(nx, algorithm)(reference, weight=reference_weight, **kwargs)
            with pytest.raises(TypeError) as actual:
                getattr(fnx, algorithm)(graph, weight=actual_weight, **kwargs)
            assert actual.value.args == expected.value.args


@pytest.mark.parametrize("algorithm,native_helper", WEIGHTED_CONSUMERS)
def test_weighted_consumers_propagate_callback_errors(
    graph_class, algorithm, native_helper, native_calls
):
    reference, graph = _exact_weight_twins(graph_class, (100, 1, 2))
    failure = ValueError("weight callback failed")

    def fail(u, v, data):
        raise failure

    kwargs = _consumer_kwargs(algorithm)
    with pytest.raises(ValueError) as expected:
        getattr(nx, algorithm)(reference, weight=fail, **kwargs)
    assert expected.value is failure
    for candidate in (graph, reference):
        before = native_calls[native_helper]
        with pytest.raises(ValueError) as actual:
            getattr(fnx, algorithm)(candidate, weight=fail, **kwargs)
        assert actual.value is failure
        assert native_calls[native_helper] == before


@pytest.mark.parametrize("algorithm,native_helper", WEIGHTED_CONSUMERS)
def test_weighted_consumers_callbacks_observe_live_input(
    graph_class, algorithm, native_helper, native_calls
):
    def build(module):
        graph = getattr(module, graph_class)()
        graph.add_nodes_from(range(4))
        graph.add_weighted_edges_from([
            (0, 1, 1), (0, 2, 1), (1, 3, 5), (2, 3, 1),
        ])
        return graph

    def weight_and_trace(graph):
        read_weight = _callback_weight(graph)
        calls = []

        def weight(u, v, data):
            if (u, v) == (0, 1):
                if graph.is_multigraph():
                    for attrs in graph[1][3].values():
                        attrs["weight"] = 0.5
                else:
                    graph[1][3]["weight"] = 0.5
            value = read_weight(u, v, data)
            calls.append((u, v, value))
            return value

        return weight, calls

    kwargs = _consumer_kwargs(algorithm)
    reference = build(nx)
    reference_weight, expected_calls = weight_and_trace(reference)
    expected = getattr(nx, algorithm)(reference, weight=reference_weight, **kwargs)
    for module in (fnx, nx):
        graph = build(module)
        weight, actual_calls = weight_and_trace(graph)
        before = native_calls[native_helper]
        actual = getattr(fnx, algorithm)(graph, weight=weight, **kwargs)
        assert actual == expected
        assert actual_calls == expected_calls
        assert native_calls[native_helper] == before
