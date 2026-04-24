"""Focused NetworkX-vs-FrankenNetworkX conformance matrices.

These tables exercise API families that are not covered by the concurrent
review-mode workstream: graph properties, traversal, and seeded random
generators.
"""

from __future__ import annotations

import math

import networkx as nx
import pytest

import franken_networkx as fnx


def _graph_signature(graph):
    def edge_endpoints(u, v):
        endpoints = (repr(u), repr(v))
        if graph.is_directed():
            return endpoints
        return tuple(sorted(endpoints))

    if graph.is_multigraph():
        edges = [
            (
                *edge_endpoints(u, v),
                repr(key),
                tuple(sorted((repr(k), repr(vv)) for k, vv in data.items())),
            )
            for u, v, key, data in graph.edges(keys=True, data=True)
        ]
    else:
        edges = [
            (
                *edge_endpoints(u, v),
                tuple(sorted((repr(k), repr(vv)) for k, vv in data.items())),
            )
            for u, v, data in graph.edges(data=True)
        ]
    return (
        type(graph).__name__,
        graph.is_directed(),
        graph.is_multigraph(),
        sorted(repr(node) for node in graph.nodes()),
        sorted(edges),
    )


def _normalize_result(value):
    if hasattr(value, "nodes") and hasattr(value, "edges"):
        return _graph_signature(value)
    if isinstance(value, float):
        if math.isnan(value):
            return "nan"
        return pytest.approx(value)
    if isinstance(value, (list, tuple)):
        return type(value)(_normalize_result(item) for item in value)
    if isinstance(value, dict):
        return {
            repr(key): _normalize_result(item)
            for key, item in sorted(value.items(), key=lambda item: repr(item[0]))
        }
    if isinstance(value, set):
        return sorted(_normalize_result(item) for item in value)
    return value


def _call_outcome(call):
    try:
        value = call()
    except Exception as exc:  # noqa: BLE001 - differential harness records contract
        return ("error", type(exc).__name__, str(exc))
    return ("ok", _normalize_result(value))


def _assert_same_outcome(fnx_call, nx_call):
    assert _call_outcome(fnx_call) == _call_outcome(nx_call)


def _graph_property_fixtures():
    fixtures = []

    for fnx_graph, nx_graph in [
        (fnx.Graph(), nx.Graph()),
        (fnx.Graph(), nx.Graph()),
        (fnx.path_graph(5), nx.path_graph(5)),
        (fnx.cycle_graph(6), nx.cycle_graph(6)),
        (fnx.complete_graph(4), nx.complete_graph(4)),
        (fnx.star_graph(4), nx.star_graph(4)),
        (fnx.DiGraph(), nx.DiGraph()),
        (fnx.MultiGraph(), nx.MultiGraph()),
    ]:
        fixtures.append((fnx_graph, nx_graph))

    fixtures[1][0].add_node("solo")
    fixtures[1][1].add_node("solo")

    for graph in fixtures[6]:
        graph.add_edges_from([(0, 1), (1, 2), (2, 0)])

    for graph in fixtures[7]:
        graph.add_edge("a", "b")
        graph.add_edge("a", "b")
        graph.add_node("c")

    disconnected_fnx = fnx.Graph()
    disconnected_nx = nx.Graph()
    for graph in (disconnected_fnx, disconnected_nx):
        graph.add_edges_from([(0, 1), (2, 3)])
    fixtures.append((disconnected_fnx, disconnected_nx))

    return fixtures


@pytest.mark.parametrize("fixture_index", range(9))
@pytest.mark.parametrize(
    "function_name", ["density", "diameter", "radius", "center", "periphery"]
)
def test_graph_properties_match_networkx_matrix(fixture_index, function_name):
    fnx_graph, nx_graph = _graph_property_fixtures()[fixture_index]
    _assert_same_outcome(
        lambda: getattr(fnx, function_name)(fnx_graph),
        lambda: getattr(nx, function_name)(nx_graph),
    )


def _traversal_fixtures():
    path_fnx = fnx.path_graph(5)
    path_nx = nx.path_graph(5)

    branch_fnx = fnx.Graph()
    branch_nx = nx.Graph()
    for graph in (branch_fnx, branch_nx):
        graph.add_edges_from([(0, 1), (0, 2), (1, 3), (1, 4), (2, 5)])

    disconnected_fnx = fnx.Graph()
    disconnected_nx = nx.Graph()
    for graph in (disconnected_fnx, disconnected_nx):
        graph.add_edges_from([(0, 1), (2, 3)])

    dag_fnx = fnx.DiGraph()
    dag_nx = nx.DiGraph()
    for graph in (dag_fnx, dag_nx):
        graph.add_edges_from([("s", "a"), ("s", "b"), ("a", "c"), ("b", "c")])

    cycle_fnx = fnx.DiGraph()
    cycle_nx = nx.DiGraph()
    for graph in (cycle_fnx, cycle_nx):
        graph.add_edges_from([(0, 1), (1, 2), (2, 0)])

    return {
        "path": (path_fnx, path_nx),
        "branch": (branch_fnx, branch_nx),
        "disconnected": (disconnected_fnx, disconnected_nx),
        "dag": (dag_fnx, dag_nx),
        "cycle": (cycle_fnx, cycle_nx),
    }


TRAVERSAL_CASES = [
    ("path", "bfs_edges", lambda mod, graph: list(mod.bfs_edges(graph, 0))),
    (
        "branch",
        "bfs_edges_depth",
        lambda mod, graph: list(mod.bfs_edges(graph, 0, depth_limit=1)),
    ),
    ("branch", "bfs_successors", lambda mod, graph: list(mod.bfs_successors(graph, 0))),
    (
        "branch",
        "bfs_predecessors",
        lambda mod, graph: list(mod.bfs_predecessors(graph, 0)),
    ),
    ("path", "dfs_edges", lambda mod, graph: list(mod.dfs_edges(graph, source=0))),
    (
        "disconnected",
        "dfs_edges_all_components",
        lambda mod, graph: list(mod.dfs_edges(graph)),
    ),
    (
        "branch",
        "dfs_preorder_nodes",
        lambda mod, graph: list(mod.dfs_preorder_nodes(graph, source=0)),
    ),
    ("dag", "topological_sort", lambda mod, graph: list(mod.topological_sort(graph))),
    ("cycle", "topological_sort_cycle", lambda mod, graph: list(mod.topological_sort(graph))),
]


@pytest.mark.parametrize(("fixture_name", "case_name", "call"), TRAVERSAL_CASES)
def test_traversal_matches_networkx_matrix(fixture_name, case_name, call):
    if case_name == "topological_sort":
        pytest.xfail("franken_networkx-codtrav-review: topological_sort tie-break order")
    fnx_graph, nx_graph = _traversal_fixtures()[fixture_name]
    _assert_same_outcome(lambda: call(fnx, fnx_graph), lambda: call(nx, nx_graph))


GENERATOR_CASES = [
    (
        "erdos_empty",
        lambda mod: mod.erdos_renyi_graph(0, 0.5, seed=11),
    ),
    (
        "erdos_dense",
        lambda mod: mod.erdos_renyi_graph(6, 1.0, seed=11),
    ),
    (
        "erdos_seeded",
        lambda mod: mod.erdos_renyi_graph(10, 0.35, seed=42),
    ),
    (
        "erdos_directed",
        lambda mod: mod.erdos_renyi_graph(8, 0.3, seed=42, directed=True),
    ),
    (
        "fast_gnp",
        lambda mod: mod.fast_gnp_random_graph(10, 0.25, seed=7),
    ),
    (
        "gnp_directed",
        lambda mod: mod.gnp_random_graph(8, 0.25, seed=7, directed=True),
    ),
    (
        "watts_ring",
        lambda mod: mod.watts_strogatz_graph(10, 4, 0.0, seed=5),
    ),
    (
        "watts_rewired",
        lambda mod: mod.watts_strogatz_graph(12, 4, 0.3, seed=5),
    ),
    (
        "barabasi_seeded",
        lambda mod: mod.barabasi_albert_graph(10, 2, seed=5),
    ),
]


@pytest.mark.parametrize(("case_name", "factory"), GENERATOR_CASES)
def test_seeded_random_generators_match_networkx_matrix(case_name, factory):
    _assert_same_outcome(lambda: factory(fnx), lambda: factory(nx))
