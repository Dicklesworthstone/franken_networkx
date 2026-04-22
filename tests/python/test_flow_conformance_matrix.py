"""Table-driven flow conformance matrix against upstream NetworkX."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import cast

import pytest


def _round_number(value):
    if value == float("inf"):
        return value
    if isinstance(value, float):
        return round(value, 9)
    return value


def _build_capacity_pair(
    fnx,
    nx,
    family: str,
    edges: list[tuple[object, object, float | None]],
):
    g_fnx = getattr(fnx, family)()
    g_nx = getattr(nx, family)()
    for graph in (g_fnx, g_nx):
        for u, v, capacity in edges:
            if capacity is None:
                graph.add_edge(u, v)
            else:
                graph.add_edge(u, v, capacity=capacity)
    return g_fnx, g_nx


def _directed_capacity_pair(fnx, nx):
    return _build_capacity_pair(
        fnx,
        nx,
        "DiGraph",
        [
            ("s", "a", 3.0),
            ("s", "b", 2.0),
            ("a", "b", 1.0),
            ("a", "t", 2.0),
            ("b", "t", 3.0),
        ],
    )


def _undirected_capacity_pair(fnx, nx):
    return _build_capacity_pair(
        fnx,
        nx,
        "Graph",
        [
            ("a", "b", 1.0),
            ("a", "c", 4.0),
            ("b", "c", 2.0),
            ("b", "d", 5.0),
            ("c", "d", 1.0),
        ],
    )


def _reverse_only_pair(fnx, nx):
    return _build_capacity_pair(
        fnx,
        nx,
        "DiGraph",
        [
            ("a", "s", 5.0),
            ("a", "t", 5.0),
        ],
    )


def _single_edge_pair(fnx, nx):
    return _build_capacity_pair(
        fnx,
        nx,
        "DiGraph",
        [
            ("s", "a", 3.0),
            ("a", "t", 2.0),
        ],
    )


def _missing_endpoint_pair(fnx, nx):
    return _build_capacity_pair(
        fnx,
        nx,
        "DiGraph",
        [
            ("a", "b", 1.0),
        ],
    )


def _infinite_capacity_pair(fnx, nx):
    return _build_capacity_pair(
        fnx,
        nx,
        "DiGraph",
        [
            ("s", "a", None),
            ("a", "t", None),
        ],
    )


def _normalize_residual(residual):
    return {
        "algorithm": residual.graph.get("algorithm"),
        "flow_value": _round_number(residual.graph.get("flow_value")),
        "inf": _round_number(residual.graph.get("inf")),
        "edges": sorted(
            (
                str(u),
                str(v),
                _round_number(attrs.get("capacity")),
                _round_number(attrs.get("flow")),
            )
            for u, v, attrs in residual.edges(data=True)
        ),
    }


def _normalize_flow_result(result):
    value, flow_dict = cast(tuple[object, dict[object, dict[object, object]]], result)
    normalized = {
        str(node): {
            str(neighbor): _round_number(flow)
            for neighbor, flow in sorted(inner.items(), key=lambda item: str(item[0]))
        }
        for node, inner in sorted(flow_dict.items(), key=lambda item: str(item[0]))
    }
    return _round_number(value), normalized


def _normalize_cut(result):
    value, partition = cast(tuple[object, tuple[set[object], set[object]]], result)
    left, right = partition
    return (
        _round_number(value),
        tuple(sorted(str(node) for node in left)),
        tuple(sorted(str(node) for node in right)),
    )


def _assert_same_result_or_exception(
    fnx_call: Callable[[], object],
    nx_call: Callable[[], object],
    *,
    normalizer: Callable[[object], object] | None = None,
) -> None:
    try:
        nx_result = nx_call()
    except Exception as nx_exc:
        with pytest.raises(Exception) as fnx_exc_info:
            fnx_call()
        fnx_exc = fnx_exc_info.value
        assert type(fnx_exc).__name__ == type(nx_exc).__name__
        assert str(fnx_exc) == str(nx_exc)
        return

    fnx_result = fnx_call()
    if normalizer is None:
        assert fnx_result == nx_result
        return
    assert normalizer(fnx_result) == normalizer(nx_result)


@dataclass(frozen=True)
class FlowConformanceCase:
    fixture_name: str
    algorithm: str
    builder: Callable[[object, object], tuple[object, object]]
    fnx_call: Callable[[object, object], object]
    nx_call: Callable[[object, object], object]
    normalizer: Callable[[object], object] | None = None


FLOW_CASES = (
    FlowConformanceCase(
        fixture_name="edmonds_karp_residual_directed",
        algorithm="edmonds_karp",
        builder=_directed_capacity_pair,
        fnx_call=lambda mod, graph: mod.edmonds_karp(graph, "s", "t"),
        nx_call=lambda mod, graph: mod.algorithms.flow.edmonds_karp(graph, "s", "t"),
        normalizer=_normalize_residual,
    ),
    FlowConformanceCase(
        fixture_name="edmonds_karp_cutoff_directed",
        algorithm="edmonds_karp",
        builder=_directed_capacity_pair,
        fnx_call=lambda mod, graph: mod.edmonds_karp(graph, "s", "t", cutoff=3.0),
        nx_call=lambda mod, graph: mod.algorithms.flow.edmonds_karp(graph, "s", "t", cutoff=3.0),
        normalizer=_normalize_residual,
    ),
    FlowConformanceCase(
        fixture_name="shortest_augmenting_path_residual_directed",
        algorithm="shortest_augmenting_path",
        builder=_directed_capacity_pair,
        fnx_call=lambda mod, graph: mod.shortest_augmenting_path(graph, "s", "t"),
        nx_call=lambda mod, graph: mod.algorithms.flow.shortest_augmenting_path(graph, "s", "t"),
        normalizer=_normalize_residual,
    ),
    FlowConformanceCase(
        fixture_name="preflow_push_residual_directed",
        algorithm="preflow_push",
        builder=_directed_capacity_pair,
        fnx_call=lambda mod, graph: mod.preflow_push(graph, "s", "t"),
        nx_call=lambda mod, graph: mod.algorithms.flow.preflow_push(graph, "s", "t"),
        normalizer=_normalize_residual,
    ),
    FlowConformanceCase(
        fixture_name="dinitz_residual_directed",
        algorithm="dinitz",
        builder=_directed_capacity_pair,
        fnx_call=lambda mod, graph: mod.dinitz(graph, "s", "t"),
        nx_call=lambda mod, graph: mod.algorithms.flow.dinitz(graph, "s", "t"),
        normalizer=_normalize_residual,
    ),
    FlowConformanceCase(
        fixture_name="boykov_kolmogorov_residual_directed",
        algorithm="boykov_kolmogorov",
        builder=_directed_capacity_pair,
        fnx_call=lambda mod, graph: mod.boykov_kolmogorov(graph, "s", "t"),
        nx_call=lambda mod, graph: mod.algorithms.flow.boykov_kolmogorov(graph, "s", "t"),
        normalizer=_normalize_residual,
    ),
    FlowConformanceCase(
        fixture_name="maximum_flow_directed_capacity_contract",
        algorithm="maximum_flow",
        builder=_directed_capacity_pair,
        fnx_call=lambda mod, graph: mod.maximum_flow(graph, "s", "t"),
        nx_call=lambda mod, graph: mod.maximum_flow(graph, "s", "t"),
        normalizer=_normalize_flow_result,
    ),
    FlowConformanceCase(
        fixture_name="maximum_flow_value_directed_capacity_contract",
        algorithm="maximum_flow_value",
        builder=_directed_capacity_pair,
        fnx_call=lambda mod, graph: mod.maximum_flow_value(graph, "s", "t"),
        nx_call=lambda mod, graph: mod.maximum_flow_value(graph, "s", "t"),
        normalizer=_round_number,
    ),
    FlowConformanceCase(
        fixture_name="minimum_cut_directed_capacity_contract",
        algorithm="minimum_cut",
        builder=_directed_capacity_pair,
        fnx_call=lambda mod, graph: mod.minimum_cut(graph, "s", "t"),
        nx_call=lambda mod, graph: mod.minimum_cut(graph, "s", "t"),
        normalizer=_normalize_cut,
    ),
    FlowConformanceCase(
        fixture_name="minimum_cut_value_directed_capacity_contract",
        algorithm="minimum_cut_value",
        builder=_directed_capacity_pair,
        fnx_call=lambda mod, graph: mod.minimum_cut_value(graph, "s", "t"),
        nx_call=lambda mod, graph: mod.minimum_cut_value(graph, "s", "t"),
        normalizer=_round_number,
    ),
    FlowConformanceCase(
        fixture_name="maximum_flow_undirected_capacity_contract",
        algorithm="maximum_flow",
        builder=_undirected_capacity_pair,
        fnx_call=lambda mod, graph: mod.maximum_flow(graph, "a", "d", capacity="capacity"),
        nx_call=lambda mod, graph: mod.maximum_flow(graph, "a", "d", capacity="capacity"),
        normalizer=_normalize_flow_result,
    ),
    FlowConformanceCase(
        fixture_name="minimum_cut_flow_func_selector_shortest_augmenting_path",
        algorithm="minimum_cut",
        builder=_directed_capacity_pair,
        fnx_call=lambda mod, graph: mod.minimum_cut(
            graph, "s", "t", flow_func=mod.shortest_augmenting_path
        ),
        nx_call=lambda mod, graph: mod.minimum_cut(
            graph, "s", "t", flow_func=mod.algorithms.flow.shortest_augmenting_path
        ),
        normalizer=_normalize_cut,
    ),
    FlowConformanceCase(
        fixture_name="minimum_cut_value_flow_func_selector_shortest_augmenting_path",
        algorithm="minimum_cut_value",
        builder=_directed_capacity_pair,
        fnx_call=lambda mod, graph: mod.minimum_cut_value(
            graph, "s", "t", flow_func=mod.shortest_augmenting_path
        ),
        nx_call=lambda mod, graph: mod.minimum_cut_value(
            graph, "s", "t", flow_func=mod.algorithms.flow.shortest_augmenting_path
        ),
        normalizer=_round_number,
    ),
    FlowConformanceCase(
        fixture_name="edmonds_karp_infinite_capacity_error_contract",
        algorithm="edmonds_karp",
        builder=_infinite_capacity_pair,
        fnx_call=lambda mod, graph: mod.edmonds_karp(graph, "s", "t"),
        nx_call=lambda mod, graph: mod.algorithms.flow.edmonds_karp(graph, "s", "t"),
    ),
    FlowConformanceCase(
        fixture_name="maximum_flow_same_source_sink_error_contract",
        algorithm="maximum_flow",
        builder=_single_edge_pair,
        fnx_call=lambda mod, graph: mod.maximum_flow(graph, "s", "s"),
        nx_call=lambda mod, graph: mod.maximum_flow(graph, "s", "s"),
    ),
    FlowConformanceCase(
        fixture_name="minimum_cut_missing_endpoint_error_contract",
        algorithm="minimum_cut",
        builder=_missing_endpoint_pair,
        fnx_call=lambda mod, graph: mod.minimum_cut(graph, "s", "b"),
        nx_call=lambda mod, graph: mod.minimum_cut(graph, "s", "b"),
    ),
    FlowConformanceCase(
        fixture_name="maximum_flow_respects_edge_direction",
        algorithm="maximum_flow",
        builder=_reverse_only_pair,
        fnx_call=lambda mod, graph: mod.maximum_flow(graph, "s", "t"),
        nx_call=lambda mod, graph: mod.maximum_flow(graph, "s", "t"),
        normalizer=_normalize_flow_result,
    ),
)


@pytest.mark.conformance
class TestFlowConformanceMatrix:
    @pytest.mark.parametrize(
        "case",
        FLOW_CASES,
        ids=[case.fixture_name for case in FLOW_CASES],
    )
    def test_flow_matrix_matches_networkx(self, fnx, nx, case):
        graph_fnx, graph_nx = case.builder(fnx, nx)
        _assert_same_result_or_exception(
            lambda: case.fnx_call(fnx, graph_fnx),
            lambda: case.nx_call(nx, graph_nx),
            normalizer=case.normalizer,
        )

    def test_flow_matrix_covers_core_algorithms(self):
        assert {case.algorithm for case in FLOW_CASES} >= {
            "edmonds_karp",
            "shortest_augmenting_path",
            "preflow_push",
            "dinitz",
            "boykov_kolmogorov",
            "maximum_flow",
            "maximum_flow_value",
            "minimum_cut",
            "minimum_cut_value",
        }
