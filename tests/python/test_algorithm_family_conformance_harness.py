"""Per-algorithm differential conformance harness.

This harness runs the same graph inputs through FrankenNetworkX and the
reference NetworkX package, then compares the observable results. It is
deliberately table-driven so adding a new algorithm is one case row, not a
bespoke test.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from itertools import islice
import math
from typing import Any

import networkx as nx
import pytest

import franken_networkx as fnx


@dataclass(frozen=True)
class GraphCase:
    name: str
    build: Callable[[Any], Any]


@dataclass(frozen=True)
class AlgorithmCase:
    family: str
    name: str
    fixtures: tuple[str, ...]
    call: Callable[[Any, Any], Any]
    comparator: Callable[[Any, Any], None]
    expected_divergence: str | None = None

    @property
    def id(self) -> str:
        return f"{self.family}:{self.name}"


@dataclass(frozen=True)
class Outcome:
    status: str
    payload: Any


def _path(module: Any) -> Any:
    return module.path_graph(5)


def _cycle(module: Any) -> Any:
    return module.cycle_graph(6)


def _complete(module: Any) -> Any:
    return module.complete_graph(4)


def _weighted(module: Any) -> Any:
    graph = module.Graph()
    graph.add_weighted_edges_from(
        [(0, 1, 1.5), (1, 2, 2.0), (0, 2, 5.0), (2, 3, 1.0), (3, 4, 0.5)]
    )
    return graph


def _directed_path(module: Any) -> Any:
    graph = module.DiGraph()
    graph.add_weighted_edges_from(
        [(0, 1, 1.0), (1, 2, 2.0), (0, 2, 4.0), (2, 3, 1.0)]
    )
    return graph


def _directed_cycle_tail(module: Any) -> Any:
    graph = module.DiGraph()
    graph.add_weighted_edges_from(
        [(0, 1, 1.0), (1, 2, 1.0), (2, 0, 1.0), (2, 3, 2.0)]
    )
    return graph


def _disconnected(module: Any) -> Any:
    graph = module.Graph()
    graph.add_edges_from([(0, 1), (1, 2), (3, 4)])
    return graph


def _multigraph(module: Any) -> Any:
    graph = module.MultiGraph()
    graph.add_edge(0, 1, key=0, weight=2.0)
    graph.add_edge(0, 1, key=1, weight=0.5)
    graph.add_edge(1, 2, key=0, weight=1.0)
    graph.add_edge(2, 3, key=0, weight=3.0)
    return graph


def _barbell(module: Any) -> Any:
    return module.barbell_graph(4, 2)


GRAPH_CASES: dict[str, GraphCase] = {
    case.name: case
    for case in (
        GraphCase("path", _path),
        GraphCase("cycle", _cycle),
        GraphCase("complete", _complete),
        GraphCase("weighted", _weighted),
        GraphCase("directed-path", _directed_path),
        GraphCase("directed-cycle-tail", _directed_cycle_tail),
        GraphCase("disconnected", _disconnected),
        GraphCase("multigraph", _multigraph),
        GraphCase("barbell", _barbell),
    )
}


def _nodes(graph: Any) -> list[Any]:
    return list(graph.nodes())


def _source(graph: Any) -> Any:
    return _nodes(graph)[0]


def _target(graph: Any) -> Any:
    return _nodes(graph)[-1]


def _personalization(graph: Any) -> dict[Any, float]:
    nodes = _nodes(graph)
    return {node: 2.0 if node == nodes[0] else 1.0 for node in nodes}


def _nstart(graph: Any) -> dict[Any, float]:
    nodes = _nodes(graph)
    return {node: float(idx + 1) for idx, node in enumerate(nodes)}


def _dangling(graph: Any) -> dict[Any, float]:
    return {node: 1.0 for node in graph.nodes()}


def _run(module: Any, graph: Any, call: Callable[[Any, Any], Any]) -> Outcome:
    try:
        return Outcome("ok", call(module, graph))
    except Exception as exc:  # noqa: BLE001 - exception contracts are parity.
        return Outcome("err", (type(exc).__name__, str(exc)))


def _materialize(value: Any) -> Any:
    if isinstance(value, Mapping):
        return value
    if isinstance(value, (str, bytes)):
        return value
    if isinstance(value, Iterable):
        return list(value)
    return value


def _assert_number_close(actual: Any, expected: Any, *, rel: float, abs_: float) -> None:
    if isinstance(actual, bool) or isinstance(expected, bool):
        assert actual == expected
        return
    if isinstance(actual, int) and isinstance(expected, int):
        assert actual == expected
        assert actual.__class__ is expected.__class__
        return
    if isinstance(actual, (int, float)) and isinstance(expected, (int, float)):
        if math.isnan(float(expected)):
            assert math.isnan(float(actual))
            return
        assert math.isclose(float(actual), float(expected), rel_tol=rel, abs_tol=abs_), (
            f"numeric mismatch: fnx={actual!r} nx={expected!r}"
        )
        return
    assert actual == expected


def _assert_equivalent(actual: Any, expected: Any, *, rel: float = 1e-7, abs_: float = 1e-9) -> None:
    actual = _materialize(actual)
    expected = _materialize(expected)

    if isinstance(actual, Mapping) and isinstance(expected, Mapping):
        assert list(actual.keys()) == list(expected.keys()), (
            f"mapping key/order mismatch: fnx={list(actual.keys())!r} "
            f"nx={list(expected.keys())!r}"
        )
        for key in expected:
            _assert_equivalent(actual[key], expected[key], rel=rel, abs_=abs_)
        return

    if isinstance(actual, (set, frozenset)) and isinstance(expected, (set, frozenset)):
        assert {
            _canonical_unordered(item) for item in actual
        } == {_canonical_unordered(item) for item in expected}
        return

    if isinstance(actual, (list, tuple)) and isinstance(expected, (list, tuple)):
        assert len(actual) == len(expected), f"length mismatch: fnx={actual!r} nx={expected!r}"
        for left, right in zip(actual, expected, strict=True):
            _assert_equivalent(left, right, rel=rel, abs_=abs_)
        return

    _assert_number_close(actual, expected, rel=rel, abs_=abs_)


def _canonical_unordered(value: Any) -> Any:
    if isinstance(value, Mapping):
        return tuple(
            sorted(
                ((_canonical_unordered(key), _canonical_unordered(val)) for key, val in value.items()),
                key=repr,
            )
        )
    if isinstance(value, (set, frozenset)):
        return tuple(sorted((_canonical_unordered(item) for item in value), key=repr))
    if isinstance(value, (list, tuple)):
        return tuple(_canonical_unordered(item) for item in value)
    if isinstance(value, float):
        if math.isnan(value):
            return ("float", "nan")
        if math.isinf(value):
            return ("float", "inf" if value > 0 else "-inf")
        return round(value, 10)
    return value


def _assert_partition_equal(actual: Any, expected: Any) -> None:
    def normalize(partition: Any) -> tuple[tuple[Any, ...], ...]:
        return tuple(sorted(tuple(sorted(group, key=repr)) for group in partition))

    assert normalize(actual) == normalize(expected), (
        f"partition mismatch: fnx={normalize(actual)!r} nx={normalize(expected)!r}"
    )


def _assert_outcome_equivalent(
    actual: Outcome,
    expected: Outcome,
    comparator: Callable[[Any, Any], None],
    expected_divergence: str | None,
) -> None:
    if actual.status != expected.status:
        if expected_divergence:
            pytest.xfail(expected_divergence)
        assert actual.status == expected.status, f"fnx={actual!r} nx={expected!r}"

    if actual.status == "err":
        if actual.payload != expected.payload and expected_divergence:
            pytest.xfail(expected_divergence)
        assert actual.payload == expected.payload
        return

    try:
        comparator(actual.payload, expected.payload)
    except AssertionError:
        if expected_divergence:
            pytest.xfail(expected_divergence)
        raise


def _same(name: str) -> Callable[[Any, Any], Any]:
    return lambda module, graph: getattr(module, name)(graph)


def _community_call(name: str, **kwargs: Any) -> Callable[[Any, Any], Any]:
    def call(module: Any, graph: Any) -> Any:
        if module is nx:
            return getattr(nx.community, name)(graph, **kwargs)
        return getattr(module, name)(graph, **kwargs)

    return call


def _default_comparator(actual: Any, expected: Any) -> None:
    _assert_equivalent(actual, expected)


def _loose_numeric_comparator(actual: Any, expected: Any) -> None:
    _assert_equivalent(actual, expected, rel=1e-5, abs_=1e-7)


def _pagerank_comparator(actual: Any, expected: Any) -> None:
    _assert_equivalent(actual, expected, rel=1e-6, abs_=1e-8)


def _partition_comparator(actual: Any, expected: Any) -> None:
    _assert_partition_equal(actual, expected)


def _centrality_cases() -> list[AlgorithmCase]:
    centrality_fixtures = ("path", "cycle", "complete", "weighted")
    directed_fixtures = ("directed-path", "directed-cycle-tail")
    spectral_fixtures = ("path", "cycle", "complete", "weighted")
    return [
        AlgorithmCase("centrality", "degree_centrality", centrality_fixtures, _same("degree_centrality"), _default_comparator),
        AlgorithmCase("centrality", "in_degree_centrality", directed_fixtures, _same("in_degree_centrality"), _default_comparator),
        AlgorithmCase("centrality", "out_degree_centrality", directed_fixtures, _same("out_degree_centrality"), _default_comparator),
        AlgorithmCase("centrality", "closeness_centrality", centrality_fixtures, _same("closeness_centrality"), _default_comparator),
        AlgorithmCase("centrality", "harmonic_centrality", centrality_fixtures, _same("harmonic_centrality"), _default_comparator),
        AlgorithmCase("centrality", "betweenness_centrality", centrality_fixtures, _same("betweenness_centrality"), _default_comparator),
        AlgorithmCase("centrality", "edge_betweenness_centrality", centrality_fixtures, _same("edge_betweenness_centrality"), _default_comparator),
        AlgorithmCase(
            "centrality",
            "eigenvector_centrality",
            spectral_fixtures,
            lambda module, graph: module.eigenvector_centrality(graph, max_iter=1000),
            _loose_numeric_comparator,
        ),
        AlgorithmCase(
            "centrality",
            "katz_centrality",
            spectral_fixtures,
            lambda module, graph: module.katz_centrality(
                graph, alpha=0.05, beta=1.0, max_iter=1000, tol=1e-8
            ),
            _loose_numeric_comparator,
        ),
        AlgorithmCase(
            "centrality",
            "hits",
            ("path", "cycle"),
            lambda module, graph: module.hits(
                graph,
                max_iter=1000,
                tol=1e-8,
                nstart=_nstart(graph),
                normalized=True,
            ),
            _loose_numeric_comparator,
        ),
    ]


def _pagerank_cases() -> list[AlgorithmCase]:
    pagerank_fixtures = ("path", "weighted", "directed-cycle-tail", "multigraph")
    return [
        AlgorithmCase(
            "pagerank",
            "default",
            pagerank_fixtures,
            lambda module, graph: module.pagerank(graph, max_iter=1000, tol=1e-8),
            _pagerank_comparator,
        ),
        AlgorithmCase(
            "pagerank",
            "unweighted",
            pagerank_fixtures,
            lambda module, graph: module.pagerank(graph, weight=None, max_iter=1000, tol=1e-8),
            _pagerank_comparator,
        ),
        AlgorithmCase(
            "pagerank",
            "weighted",
            ("weighted", "directed-cycle-tail", "multigraph"),
            lambda module, graph: module.pagerank(graph, weight="weight", max_iter=1000, tol=1e-8),
            _pagerank_comparator,
        ),
        AlgorithmCase(
            "pagerank",
            "personalization",
            ("path", "directed-cycle-tail"),
            lambda module, graph: module.pagerank(
                graph,
                personalization=_personalization(graph),
                max_iter=1000,
                tol=1e-8,
            ),
            _pagerank_comparator,
        ),
        AlgorithmCase(
            "pagerank",
            "nstart_and_dangling",
            ("path", "directed-cycle-tail"),
            lambda module, graph: module.pagerank(
                graph,
                nstart=_nstart(graph),
                dangling=_dangling(graph),
                max_iter=1000,
                tol=1e-8,
            ),
            _pagerank_comparator,
        ),
    ]


def _shortest_path_cases() -> list[AlgorithmCase]:
    fixtures = ("path", "weighted", "directed-path")
    return [
        AlgorithmCase("shortest-path", "has_path", fixtures, lambda module, graph: module.has_path(graph, _source(graph), _target(graph)), _default_comparator),
        AlgorithmCase("shortest-path", "shortest_path", fixtures, lambda module, graph: module.shortest_path(graph, _source(graph), _target(graph)), _default_comparator),
        AlgorithmCase("shortest-path", "shortest_path_length", fixtures, lambda module, graph: module.shortest_path_length(graph, _source(graph), _target(graph)), _default_comparator),
        AlgorithmCase("shortest-path", "shortest_path_weighted", ("weighted", "directed-path"), lambda module, graph: module.shortest_path(graph, _source(graph), _target(graph), weight="weight"), _default_comparator),
        AlgorithmCase("shortest-path", "shortest_path_length_weighted", ("weighted", "directed-path"), lambda module, graph: module.shortest_path_length(graph, _source(graph), _target(graph), weight="weight"), _default_comparator),
        AlgorithmCase("shortest-path", "dijkstra_path", ("weighted", "directed-path"), lambda module, graph: module.dijkstra_path(graph, _source(graph), _target(graph), weight="weight"), _default_comparator),
        AlgorithmCase("shortest-path", "dijkstra_path_length", ("weighted", "directed-path"), lambda module, graph: module.dijkstra_path_length(graph, _source(graph), _target(graph), weight="weight"), _default_comparator),
        AlgorithmCase("shortest-path", "bellman_ford_path", ("weighted", "directed-path"), lambda module, graph: module.bellman_ford_path(graph, _source(graph), _target(graph), weight="weight"), _default_comparator),
        AlgorithmCase("shortest-path", "bellman_ford_path_length", ("weighted", "directed-path"), lambda module, graph: module.bellman_ford_path_length(graph, _source(graph), _target(graph), weight="weight"), _default_comparator),
        AlgorithmCase("shortest-path", "single_source_shortest_path", fixtures, lambda module, graph: module.single_source_shortest_path(graph, _source(graph)), _default_comparator),
        AlgorithmCase("shortest-path", "single_source_shortest_path_length", fixtures, lambda module, graph: module.single_source_shortest_path_length(graph, _source(graph)), _default_comparator),
        AlgorithmCase("shortest-path", "all_pairs_shortest_path", fixtures, lambda module, graph: dict(module.all_pairs_shortest_path(graph)), _default_comparator),
        AlgorithmCase("shortest-path", "all_pairs_shortest_path_length", fixtures, lambda module, graph: dict(module.all_pairs_shortest_path_length(graph)), _default_comparator),
        AlgorithmCase("shortest-path", "all_shortest_paths", fixtures, lambda module, graph: list(module.all_shortest_paths(graph, _source(graph), _target(graph))), _default_comparator),
        AlgorithmCase("shortest-path", "multi_source_dijkstra", ("weighted", "directed-path"), lambda module, graph: module.multi_source_dijkstra(graph, {_source(graph)}, target=_target(graph), weight="weight"), _default_comparator),
        AlgorithmCase("shortest-path", "astar_path", ("weighted", "directed-path"), lambda module, graph: module.astar_path(graph, _source(graph), _target(graph), weight="weight"), _default_comparator),
        AlgorithmCase("shortest-path", "astar_path_length", ("weighted", "directed-path"), lambda module, graph: module.astar_path_length(graph, _source(graph), _target(graph), weight="weight"), _default_comparator),
        AlgorithmCase("shortest-path", "shortest_simple_paths", ("path", "weighted"), lambda module, graph: list(islice(module.shortest_simple_paths(graph, _source(graph), _target(graph), weight="weight"), 3)), _default_comparator),
    ]


def _community_cases() -> list[AlgorithmCase]:
    return [
        AlgorithmCase("community", "louvain_communities", ("barbell",), _community_call("louvain_communities", seed=42), _partition_comparator),
        AlgorithmCase("community", "greedy_modularity_communities", ("barbell",), _community_call("greedy_modularity_communities"), _partition_comparator),
        AlgorithmCase("community", "label_propagation_communities", ("barbell",), _community_call("label_propagation_communities"), _partition_comparator),
        AlgorithmCase(
            "community",
            "modularity",
            ("barbell",),
            lambda module, graph: (
                nx.community.modularity(graph, [set(range(0, 4)), set(range(4, 10))])
                if module is nx
                else module.modularity(graph, [set(range(0, 4)), set(range(4, 10))])
            ),
            _loose_numeric_comparator,
        ),
    ]


ALGORITHM_CASES = (
    _centrality_cases()
    + _pagerank_cases()
    + _shortest_path_cases()
    + _community_cases()
)


def _case_fixture_params() -> list[pytest.ParamSpec]:
    params = []
    for case in ALGORITHM_CASES:
        for fixture_name in case.fixtures:
            params.append(pytest.param(case, fixture_name, id=f"{case.id}:{fixture_name}"))
    return params


@pytest.mark.conformance
@pytest.mark.parametrize(("case", "fixture_name"), _case_fixture_params())
def test_algorithm_family_conformance_matrix(case: AlgorithmCase, fixture_name: str) -> None:
    graph_case = GRAPH_CASES[fixture_name]
    fnx_graph = graph_case.build(fnx)
    nx_graph = graph_case.build(nx)

    fnx_outcome = _run(fnx, fnx_graph, case.call)
    nx_outcome = _run(nx, nx_graph, case.call)

    _assert_outcome_equivalent(
        fnx_outcome,
        nx_outcome,
        case.comparator,
        case.expected_divergence,
    )
