"""Differential DAG topology conformance matrix."""

from __future__ import annotations

import networkx as nx
import pytest

import franken_networkx as fnx


DAG_FIXTURE_NAMES = [
    "empty",
    "single",
    "chain",
    "diamond",
    "disconnected",
    "weighted_choice",
    "cycle",
]


def _build_dag(module, fixture_name):
    graph = module.DiGraph()

    if fixture_name == "empty":
        return graph
    if fixture_name == "single":
        graph.add_node("a")
        return graph
    if fixture_name == "chain":
        graph.add_edges_from([("a", "b"), ("b", "c")])
        return graph
    if fixture_name == "diamond":
        graph.add_edges_from([("s", "a"), ("s", "b"), ("a", "t"), ("b", "t")])
        return graph
    if fixture_name == "disconnected":
        graph.add_edges_from([("a", "b"), ("c", "d")])
        return graph
    if fixture_name == "weighted_choice":
        graph.add_edge("s", "a", weight=2)
        graph.add_edge("a", "t", weight=3)
        graph.add_edge("s", "t", weight=10)
        return graph
    if fixture_name == "cycle":
        graph.add_edges_from([("a", "b"), ("b", "a")])
        return graph
    raise AssertionError(f"unknown fixture {fixture_name}")


def _normalize_graph(graph):
    edges = [
        (
            repr(u),
            repr(v),
            tuple(sorted((repr(key), repr(value)) for key, value in attrs.items())),
        )
        for u, v, attrs in graph.edges(data=True)
    ]
    return (
        type(graph).__name__,
        graph.is_directed(),
        graph.is_multigraph(),
        sorted(repr(node) for node in graph.nodes()),
        sorted(edges),
    )


def _normalize_value(value):
    if hasattr(value, "nodes") and hasattr(value, "edges"):
        return _normalize_graph(value)
    if isinstance(value, dict):
        return {
            repr(key): _normalize_value(item)
            for key, item in sorted(value.items(), key=lambda item: repr(item[0]))
        }
    if isinstance(value, (list, tuple)):
        return [_normalize_value(item) for item in value]
    if isinstance(value, (set, frozenset)):
        return sorted(_normalize_value(item) for item in value)
    return value


def _call_outcome(call):
    try:
        return ("ok", _normalize_value(call()))
    except Exception as exc:  # noqa: BLE001 - parity harness records contracts
        return ("error", type(exc).__name__, str(exc))


def _assert_same_outcome(fnx_call, nx_call):
    assert _call_outcome(fnx_call) == _call_outcome(nx_call)


DAG_TOPOLOGY_CALLS = [
    (
        "all_topological_sorts",
        lambda module, graph: list(module.all_topological_sorts(graph)),
    ),
    (
        "topological_generations",
        lambda module, graph: list(module.topological_generations(graph)),
    ),
    ("transitive_reduction", lambda module, graph: module.transitive_reduction(graph)),
    ("dag_to_branching", lambda module, graph: module.dag_to_branching(graph)),
    ("antichains", lambda module, graph: list(module.antichains(graph))),
    ("dag_longest_path", lambda module, graph: module.dag_longest_path(graph)),
    (
        "dag_longest_path_length",
        lambda module, graph: module.dag_longest_path_length(graph),
    ),
]


@pytest.mark.parametrize("fixture_name", DAG_FIXTURE_NAMES)
@pytest.mark.parametrize(("call_name", "call"), DAG_TOPOLOGY_CALLS)
def test_dag_topology_family_matches_networkx(fixture_name, call_name, call):
    fnx_graph = _build_dag(fnx, fixture_name)
    nx_graph = _build_dag(nx, fixture_name)

    _assert_same_outcome(lambda: call(fnx, fnx_graph), lambda: call(nx, nx_graph))
