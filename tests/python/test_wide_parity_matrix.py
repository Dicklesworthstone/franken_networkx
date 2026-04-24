"""Wide fnx-vs-NetworkX differential conformance matrix.

This is the broad first slice for the conformance-harness track.  It
intentionally exercises many public algorithms over the same small graph
families so future parity gaps show up as a compact matrix coordinate:
``algorithm × shape``.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Callable

import networkx as nx
import numpy as np
import pytest

import franken_networkx as fnx


@dataclass(frozen=True)
class GraphFixture:
    name: str
    fnx_graph: Any
    nx_graph: Any


@dataclass(frozen=True)
class AlgorithmCase:
    name: str
    call: Callable[[Any, Any], Any]


def _path(module: Any) -> Any:
    return module.path_graph(5)


def _cycle(module: Any) -> Any:
    return module.cycle_graph(5)


def _complete(module: Any) -> Any:
    return module.complete_graph(4)


def _star(module: Any) -> Any:
    return module.star_graph(4)


def _single(module: Any) -> Any:
    graph = module.Graph()
    graph.add_node(0)
    return graph


def _empty(module: Any) -> Any:
    return module.Graph()


def _disconnected(module: Any) -> Any:
    graph = module.Graph()
    graph.add_edges_from([(0, 1), (1, 2), (3, 4)])
    return graph


def _weighted(module: Any) -> Any:
    graph = module.Graph()
    graph.add_weighted_edges_from([(0, 1, 1.0), (1, 2, 2.0), (0, 2, 5.0)])
    graph.add_edge(2, 3, weight=-0.25)
    return graph


def _digraph_path(module: Any) -> Any:
    graph = module.DiGraph()
    graph.add_edges_from([(0, 1), (1, 2), (2, 3)])
    return graph


def _digraph_cycle(module: Any) -> Any:
    graph = module.DiGraph()
    graph.add_edges_from([(0, 1), (1, 2), (2, 0), (2, 3)])
    return graph


def _multigraph(module: Any) -> Any:
    graph = module.MultiGraph()
    graph.add_edge(0, 1, key=0, weight=2.0)
    graph.add_edge(0, 1, key=1, weight=0.5)
    graph.add_edge(1, 2, key=0, weight=1.0)
    return graph


def _fixtures() -> list[GraphFixture]:
    builders = [
        ("empty", _empty),
        ("single", _single),
        ("path", _path),
        ("cycle", _cycle),
        ("complete", _complete),
        ("star", _star),
        ("disconnected", _disconnected),
        ("weighted", _weighted),
        ("digraph-path", _digraph_path),
        ("digraph-cycle", _digraph_cycle),
        ("multigraph", _multigraph),
    ]
    return [GraphFixture(name, builder(fnx), builder(nx)) for name, builder in builders]


def _nodes(graph: Any) -> list[Any]:
    return list(graph.nodes())


def _source(graph: Any) -> Any:
    nodes = _nodes(graph)
    return nodes[0] if nodes else 0


def _target(graph: Any) -> Any:
    nodes = _nodes(graph)
    return nodes[-1] if nodes else 0


def _pair(graph: Any) -> tuple[Any, Any]:
    nodes = _nodes(graph)
    if len(nodes) >= 2:
        return nodes[0], nodes[-1]
    if len(nodes) == 1:
        return nodes[0], nodes[0]
    return 0, 1


def _node_set(graph: Any) -> set[Any]:
    nodes = _nodes(graph)
    return set(nodes[:2])


def _edge_tuple(graph: Any, edge: Any, directed: bool) -> Any:
    if len(edge) == 4:
        u, v, key, data = edge
        endpoints = (u, v) if directed else tuple(sorted((u, v), key=repr))
        return (*endpoints, key, _canonical(data))
    u, v, data = edge
    endpoints = (u, v) if directed else tuple(sorted((u, v), key=repr))
    return (*endpoints, _canonical(data))


def _canonical_graph(graph: Any) -> Any:
    directed = graph.is_directed()
    if graph.is_multigraph():
        edges = graph.edges(keys=True, data=True)
    else:
        edges = graph.edges(data=True)
    return (
        "graph",
        directed,
        graph.is_multigraph(),
        tuple(sorted((_canonical(node) for node in graph.nodes()), key=repr)),
        tuple(sorted((_edge_tuple(graph, edge, directed) for edge in edges), key=repr)),
    )


def _canonical(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return ("array", _canonical(value.tolist()))
    if isinstance(value, np.generic):
        return _canonical(value.item())
    if isinstance(value, (int, float)):
        number = float(value)
        if math.isnan(number):
            return ("float", "nan")
        if math.isinf(number):
            return ("float", "inf" if number > 0 else "-inf")
        return ("number", round(number, 10))
    if isinstance(value, (str, bytes, bool, type(None))):
        return value
    if hasattr(value, "nodes") and hasattr(value, "edges"):
        return _canonical_graph(value)
    if isinstance(value, dict):
        return (
            "dict",
            tuple(
                sorted(
                    ((_canonical(key), _canonical(val)) for key, val in value.items()),
                    key=repr,
                ),
            ),
        )
    if isinstance(value, (set, frozenset)):
        return ("set", tuple(sorted((_canonical(item) for item in value), key=repr)))
    if isinstance(value, tuple):
        return ("tuple", tuple(_canonical(item) for item in value))
    if isinstance(value, list):
        return ("seq", tuple(_canonical(item) for item in value))
    if hasattr(value, "__iter__") and not isinstance(value, (str, bytes)):
        return ("seq", tuple(_canonical(item) for item in value))
    return repr(value)


def _run(module: Any, graph: Any, call: Callable[[Any, Any], Any]) -> Any:
    try:
        return ("ok", _canonical(call(module, graph)))
    except Exception as exc:  # noqa: BLE001 - exception contracts are part of parity.
        return ("err", type(exc).__name__)


def _same_call(name: str) -> AlgorithmCase:
    return AlgorithmCase(name, lambda module, graph: getattr(module, name)(graph))


def _weighted_call(name: str) -> AlgorithmCase:
    return AlgorithmCase(
        f"{name}:weight",
        lambda module, graph: getattr(module, name)(graph, weight="weight"),
    )


CASES = [
    _same_call("number_of_nodes"),
    _same_call("number_of_edges"),
    _same_call("density"),
    _same_call("degree_histogram"),
    _same_call("degree"),
    _same_call("number_of_selfloops"),
    _same_call("is_directed"),
    _same_call("is_empty"),
    _same_call("is_frozen"),
    _same_call("is_weighted"),
    _same_call("is_negatively_weighted"),
    _same_call("is_connected"),
    _same_call("is_biconnected"),
    _same_call("is_tree"),
    _same_call("is_forest"),
    _same_call("connected_components"),
    _same_call("strongly_connected_components"),
    _same_call("weakly_connected_components"),
    _same_call("attracting_components"),
    _same_call("number_attracting_components"),
    _same_call("is_attracting_component"),
    _same_call("bridges"),
    _same_call("local_bridges"),
    _same_call("degree_centrality"),
    _same_call("closeness_centrality"),
    _same_call("harmonic_centrality"),
    _same_call("betweenness_centrality"),
    _same_call("pagerank"),
    _same_call("clustering"),
    _same_call("average_clustering"),
    _same_call("transitivity"),
    _same_call("triangles"),
    _same_call("square_clustering"),
    _same_call("complement"),
    _same_call("line_graph"),
    _same_call("to_undirected"),
    _same_call("to_directed"),
    AlgorithmCase("reverse", lambda module, graph: module.reverse(graph, copy=True)),
    AlgorithmCase(
        "has_path",
        lambda module, graph: module.has_path(graph, _source(graph), _target(graph)),
    ),
    AlgorithmCase(
        "shortest_path",
        lambda module, graph: module.shortest_path(graph, _source(graph), _target(graph)),
    ),
    AlgorithmCase(
        "shortest_path_length",
        lambda module, graph: module.shortest_path_length(
            graph, _source(graph), _target(graph)
        ),
    ),
    _weighted_call("shortest_path"),
    _weighted_call("shortest_path_length"),
    AlgorithmCase(
        "single_source_shortest_path",
        lambda module, graph: module.single_source_shortest_path(graph, _source(graph)),
    ),
    AlgorithmCase(
        "single_source_shortest_path_length",
        lambda module, graph: module.single_source_shortest_path_length(
            graph, _source(graph)
        ),
    ),
    AlgorithmCase(
        "single_target_shortest_path",
        lambda module, graph: module.single_target_shortest_path(graph, _target(graph)),
    ),
    AlgorithmCase(
        "single_target_shortest_path_length",
        lambda module, graph: module.single_target_shortest_path_length(
            graph, _target(graph)
        ),
    ),
    AlgorithmCase(
        "all_pairs_shortest_path",
        lambda module, graph: dict(module.all_pairs_shortest_path(graph)),
    ),
    AlgorithmCase(
        "all_pairs_shortest_path_length",
        lambda module, graph: dict(module.all_pairs_shortest_path_length(graph)),
    ),
    AlgorithmCase(
        "all_pairs_dijkstra_path",
        lambda module, graph: dict(module.all_pairs_dijkstra_path(graph)),
    ),
    AlgorithmCase(
        "all_pairs_dijkstra_path_length",
        lambda module, graph: dict(module.all_pairs_dijkstra_path_length(graph)),
    ),
    AlgorithmCase(
        "dijkstra_path",
        lambda module, graph: module.dijkstra_path(graph, _source(graph), _target(graph)),
    ),
    AlgorithmCase(
        "dijkstra_path_length",
        lambda module, graph: module.dijkstra_path_length(
            graph, _source(graph), _target(graph)
        ),
    ),
    AlgorithmCase(
        "bfs_edges",
        lambda module, graph: module.bfs_edges(graph, _source(graph)),
    ),
    AlgorithmCase(
        "dfs_edges",
        lambda module, graph: module.dfs_edges(graph, source=_source(graph)),
    ),
    AlgorithmCase(
        "bfs_predecessors",
        lambda module, graph: module.bfs_predecessors(graph, _source(graph)),
    ),
    AlgorithmCase(
        "bfs_successors",
        lambda module, graph: module.bfs_successors(graph, _source(graph)),
    ),
    AlgorithmCase(
        "bfs_tree",
        lambda module, graph: module.bfs_tree(graph, _source(graph)),
    ),
    AlgorithmCase(
        "dfs_tree",
        lambda module, graph: module.dfs_tree(graph, source=_source(graph)),
    ),
    AlgorithmCase(
        "dfs_preorder_nodes",
        lambda module, graph: module.dfs_preorder_nodes(graph, source=_source(graph)),
    ),
    AlgorithmCase(
        "dfs_postorder_nodes",
        lambda module, graph: module.dfs_postorder_nodes(graph, source=_source(graph)),
    ),
    AlgorithmCase(
        "edge_bfs",
        lambda module, graph: module.edge_bfs(graph, source=_source(graph)),
    ),
    AlgorithmCase(
        "edge_dfs",
        lambda module, graph: module.edge_dfs(graph, source=_source(graph)),
    ),
    _same_call("is_directed_acyclic_graph"),
    _same_call("topological_sort"),
    AlgorithmCase(
        "ancestors",
        lambda module, graph: module.ancestors(graph, _target(graph)),
    ),
    AlgorithmCase(
        "descendants",
        lambda module, graph: module.descendants(graph, _source(graph)),
    ),
    _same_call("non_edges"),
    AlgorithmCase(
        "common_neighbors",
        lambda module, graph: module.common_neighbors(graph, *_pair(graph)),
    ),
    AlgorithmCase(
        "jaccard_coefficient",
        lambda module, graph: module.jaccard_coefficient(graph, [_pair(graph)]),
    ),
    AlgorithmCase(
        "adamic_adar_index",
        lambda module, graph: module.adamic_adar_index(graph, [_pair(graph)]),
    ),
    AlgorithmCase(
        "resource_allocation_index",
        lambda module, graph: module.resource_allocation_index(graph, [_pair(graph)]),
    ),
    AlgorithmCase(
        "preferential_attachment",
        lambda module, graph: module.preferential_attachment(graph, [_pair(graph)]),
    ),
    AlgorithmCase(
        "is_connected_dominating_set",
        lambda module, graph: module.is_connected_dominating_set(graph, _node_set(graph)),
    ),
]


def _expected_divergence(case_name: str, fixture_name: str) -> str | None:
    directed_shortest_path = {
        "single_source_shortest_path",
        "single_source_shortest_path_length",
        "all_pairs_shortest_path",
        "all_pairs_shortest_path_length",
    }

    if case_name in {"ancestors", "descendants"} and not fixture_name.startswith("digraph"):
        return "franken_networkx-zzcm4: ancestors/descendants undirected graph contract"
    if case_name == "pagerank" and fixture_name in {"weighted", "multigraph"}:
        return "franken_networkx-zzcm5: pagerank weighted/multigraph parity"
    if case_name in directed_shortest_path and fixture_name.startswith("digraph"):
        return "franken_networkx-zzcm6: unweighted shortest-path directed graph contract"
    if (
        case_name in {"strongly_connected_components", "topological_sort"}
        and fixture_name.startswith("digraph")
    ):
        return "franken_networkx-zzcm7: directed component/topological order contract"
    if case_name == "local_bridges" and fixture_name in {
        "digraph-path",
        "digraph-cycle",
        "multigraph",
    }:
        return "franken_networkx-zzcm8: local_bridges graph-family contract"
    if fixture_name == "multigraph" and case_name in {
        "is_tree",
        "is_forest",
        "bridges",
        "degree_centrality",
        "complement",
    }:
        return "franken_networkx-zzcm9: multigraph structural algorithm contract"
    return None


@pytest.mark.parametrize("case", CASES, ids=[case.name for case in CASES])
@pytest.mark.parametrize("fixture", _fixtures(), ids=[fixture.name for fixture in _fixtures()])
def test_wide_algorithm_parity_matrix(case: AlgorithmCase, fixture: GraphFixture):
    fnx_result = _run(fnx, fixture.fnx_graph, case.call)
    nx_result = _run(nx, fixture.nx_graph, case.call)
    if fnx_result != nx_result:
        reason = _expected_divergence(case.name, fixture.name)
        if reason is not None:
            pytest.xfail(reason)
    assert fnx_result == nx_result, (
        f"{case.name} diverged on {fixture.name}\n"
        f"fnx={fnx_result!r}\n"
        f"nx={nx_result!r}"
    )
