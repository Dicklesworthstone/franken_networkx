"""Table-driven shortest-path conformance matrix against upstream NetworkX."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import pytest


def _attrs(weight: float) -> dict[str, float]:
    return {"weight": weight, "cost": weight, "length": weight}


def _build_graph_pair(
    fnx,
    nx,
    family: str,
    edges: list[tuple[Any, Any, dict[str, Any]]],
    *,
    isolated_nodes: tuple[Any, ...] = (),
):
    g_fnx = getattr(fnx, family)()
    g_nx = getattr(nx, family)()
    for graph in (g_fnx, g_nx):
        for u, v, attrs in edges:
            graph.add_edge(u, v, **attrs)
        for node in isolated_nodes:
            graph.add_node(node)
    return g_fnx, g_nx


def _unweighted_graph_pair(fnx, nx):
    return _build_graph_pair(
        fnx,
        nx,
        "Graph",
        [
            ("a", "b", {}),
            ("b", "c", {}),
            ("c", "d", {}),
            ("d", "e", {}),
        ],
    )


def _weighted_digraph_pair(fnx, nx):
    return _build_graph_pair(
        fnx,
        nx,
        "DiGraph",
        [
            ("a", "b", _attrs(2.0)),
            ("a", "c", _attrs(1.0)),
            ("c", "b", _attrs(1.0)),
            ("b", "d", _attrs(-1.0)),
            ("c", "d", _attrs(3.0)),
            ("d", "e", _attrs(2.0)),
        ],
        isolated_nodes=("isolated",),
    )


def _all_shortest_paths_graph_pair(fnx, nx):
    return _build_graph_pair(
        fnx,
        nx,
        "Graph",
        [
            ("a", "b", _attrs(1.0)),
            ("a", "c", _attrs(1.0)),
            ("b", "d", _attrs(1.0)),
            ("c", "d", _attrs(1.0)),
            ("b", "e", _attrs(2.0)),
            ("d", "e", _attrs(1.0)),
        ],
        isolated_nodes=("isolated",),
    )


def _all_shortest_paths_digraph_pair(fnx, nx):
    return _build_graph_pair(
        fnx,
        nx,
        "DiGraph",
        [
            ("a", "b", _attrs(1.0)),
            ("a", "c", _attrs(1.0)),
            ("b", "d", _attrs(1.0)),
            ("c", "d", _attrs(1.0)),
            ("b", "e", _attrs(2.0)),
            ("d", "e", _attrs(1.0)),
        ],
        isolated_nodes=("isolated",),
    )


def _weighted_multigraph_pair(fnx, nx):
    return _build_graph_pair(
        fnx,
        nx,
        "MultiGraph",
        [
            ("a", "b", _attrs(5.0)),
            ("a", "b", _attrs(1.0)),
            ("b", "c", _attrs(1.0)),
            ("c", "d", _attrs(1.0)),
            ("a", "d", _attrs(10.0)),
        ],
    )


def _weighted_multidigraph_pair(fnx, nx):
    return _build_graph_pair(
        fnx,
        nx,
        "MultiDiGraph",
        [
            ("s", "a", _attrs(6.0)),
            ("s", "a", _attrs(2.0)),
            ("a", "t", _attrs(1.0)),
            ("s", "t", _attrs(9.0)),
        ],
    )


def _disconnected_graph_pair(fnx, nx):
    return _build_graph_pair(
        fnx,
        nx,
        "Graph",
        [
            ("a", "b", {}),
            ("b", "c", {}),
            ("d", "e", {}),
        ],
    )


def _negative_cycle_digraph_pair(fnx, nx):
    return _build_graph_pair(
        fnx,
        nx,
        "DiGraph",
        [
            ("a", "b", _attrs(1.0)),
            ("b", "c", _attrs(-3.0)),
            ("c", "a", _attrs(1.0)),
        ],
    )


def _cost_weight(_u, _v, data):
    return data["cost"]


def _length_weight(_u, _v, data):
    return data["length"]


def _assert_same_result_or_exception(fnx_call: Callable[[], Any], nx_call: Callable[[], Any]) -> None:
    try:
        nx_result = nx_call()
    except Exception as nx_exc:
        with pytest.raises(Exception) as fnx_exc_info:
            fnx_call()
        fnx_exc = fnx_exc_info.value
        assert type(fnx_exc).__name__ == type(nx_exc).__name__
        assert str(fnx_exc) == str(nx_exc)
        return

    assert fnx_call() == nx_result


@dataclass(frozen=True)
class ShortestPathConformanceCase:
    fixture_name: str
    algorithm: str
    graph_family: str
    builder: Callable[[Any, Any], tuple[Any, Any]]
    call: Callable[[Any, Any], Any]


SHORTEST_PATH_CASES = (
    ShortestPathConformanceCase(
        fixture_name="shortest_path_graph_unweighted_query",
        algorithm="shortest_path",
        graph_family="Graph",
        builder=_unweighted_graph_pair,
        call=lambda mod, graph: mod.shortest_path(graph, "a", "e"),
    ),
    ShortestPathConformanceCase(
        fixture_name="shortest_path_digraph_weighted_dijkstra",
        algorithm="shortest_path",
        graph_family="DiGraph",
        builder=_weighted_digraph_pair,
        call=lambda mod, graph: mod.shortest_path(
            graph, "a", "e", weight="weight", method="dijkstra"
        ),
    ),
    ShortestPathConformanceCase(
        fixture_name="shortest_path_multigraph_uses_lowest_parallel_edge_weight",
        algorithm="shortest_path",
        graph_family="MultiGraph",
        builder=_weighted_multigraph_pair,
        call=lambda mod, graph: mod.shortest_path(graph, "a", "d", weight="weight"),
    ),
    ShortestPathConformanceCase(
        fixture_name="shortest_path_length_multidigraph_uses_lowest_parallel_edge_weight",
        algorithm="shortest_path_length",
        graph_family="MultiDiGraph",
        builder=_weighted_multidigraph_pair,
        call=lambda mod, graph: mod.shortest_path_length(graph, "s", "t", weight="weight"),
    ),
    ShortestPathConformanceCase(
        fixture_name="all_pairs_all_shortest_paths_graph_callable_weight",
        algorithm="all_pairs_all_shortest_paths",
        graph_family="Graph",
        builder=_all_shortest_paths_graph_pair,
        call=lambda mod, graph: dict(mod.all_pairs_all_shortest_paths(graph, weight=_cost_weight)),
    ),
    ShortestPathConformanceCase(
        fixture_name="single_source_all_shortest_paths_digraph_bellman_ford",
        algorithm="single_source_all_shortest_paths",
        graph_family="DiGraph",
        builder=_all_shortest_paths_digraph_pair,
        call=lambda mod, graph: dict(
            mod.single_source_all_shortest_paths(
                graph, "a", weight="weight", method="bellman-ford"
            )
        ),
    ),
    ShortestPathConformanceCase(
        fixture_name="johnson_digraph_callable_weight",
        algorithm="johnson",
        graph_family="DiGraph",
        builder=_weighted_digraph_pair,
        call=lambda mod, graph: mod.johnson(graph, weight=_cost_weight),
    ),
    ShortestPathConformanceCase(
        fixture_name="dijkstra_predecessor_and_distance_graph_cutoff_callable_weight",
        algorithm="dijkstra_predecessor_and_distance",
        graph_family="Graph",
        builder=_all_shortest_paths_graph_pair,
        call=lambda mod, graph: mod.dijkstra_predecessor_and_distance(
            graph, "a", cutoff=2.5, weight=_cost_weight
        ),
    ),
    ShortestPathConformanceCase(
        fixture_name="goldberg_radzik_digraph_callable_weight",
        algorithm="goldberg_radzik",
        graph_family="DiGraph",
        builder=_weighted_digraph_pair,
        call=lambda mod, graph: mod.goldberg_radzik(graph, "a", weight=_length_weight),
    ),
    ShortestPathConformanceCase(
        fixture_name="shortest_path_graph_no_path_error_contract",
        algorithm="shortest_path",
        graph_family="Graph",
        builder=_disconnected_graph_pair,
        call=lambda mod, graph: mod.shortest_path(graph, "a", "e"),
    ),
    ShortestPathConformanceCase(
        fixture_name="johnson_negative_cycle_error_contract",
        algorithm="johnson",
        graph_family="DiGraph",
        builder=_negative_cycle_digraph_pair,
        call=lambda mod, graph: mod.johnson(graph, weight="weight"),
    ),
)


@pytest.mark.conformance
class TestShortestPathConformanceMatrix:
    @pytest.mark.parametrize(
        "case",
        SHORTEST_PATH_CASES,
        ids=[case.fixture_name for case in SHORTEST_PATH_CASES],
    )
    def test_shortest_path_matrix_matches_networkx(self, fnx, nx, case):
        graph_fnx, graph_nx = case.builder(fnx, nx)
        _assert_same_result_or_exception(
            lambda: case.call(fnx, graph_fnx),
            lambda: case.call(nx, graph_nx),
        )

    def test_shortest_path_matrix_covers_core_algorithms_and_graph_families(self):
        assert {case.graph_family for case in SHORTEST_PATH_CASES} == {
            "Graph",
            "DiGraph",
            "MultiGraph",
            "MultiDiGraph",
        }
        assert {case.algorithm for case in SHORTEST_PATH_CASES} >= {
            "shortest_path",
            "shortest_path_length",
            "all_pairs_all_shortest_paths",
            "single_source_all_shortest_paths",
            "johnson",
            "dijkstra_predecessor_and_distance",
            "goldberg_radzik",
        }
