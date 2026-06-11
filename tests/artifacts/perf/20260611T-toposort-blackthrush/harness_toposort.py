#!/usr/bin/env python3
"""Proof and benchmark harness for br-r37-c1-04z53.62."""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import time
from pathlib import Path
from typing import Any, Callable

import franken_networkx as fnx
import networkx as nx


def _stable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _stable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_stable(item) for item in value]
    if isinstance(value, set):
        return sorted((_stable(item) for item in value), key=repr)
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return repr(value)


def _sha256(value: Any) -> str:
    encoded = json.dumps(_stable(value), sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _fixture_specs() -> list[dict[str, Any]]:
    dag450_edges: list[tuple[int, int]] = []
    for node in range(450):
        if node + 1 < 450:
            dag450_edges.append((node, node + 1))
        if node + 7 < 450:
            dag450_edges.append((node, node + 7))
        if node % 11 == 0 and node + 23 < 450:
            dag450_edges.append((node, node + 23))

    return [
        {"name": "empty", "kind": "DiGraph", "nodes": [], "edges": []},
        {"name": "single", "kind": "DiGraph", "nodes": [0], "edges": []},
        {
            "name": "chain",
            "kind": "DiGraph",
            "nodes": [],
            "edges": [(0, 1), (1, 2), (2, 3)],
        },
        {
            "name": "diamond",
            "kind": "DiGraph",
            "nodes": [],
            "edges": [(0, 1), (0, 2), (1, 3), (2, 3)],
        },
        {
            "name": "wide_fifo",
            "kind": "DiGraph",
            "nodes": [],
            "edges": [(0, 3), (1, 3), (2, 3), (3, 4), (3, 5)],
        },
        {
            "name": "disconnected_insert_order",
            "kind": "DiGraph",
            "nodes": [0],
            "edges": [(2, 4), (1, 4), (3, 5)],
        },
        {
            "name": "strings",
            "kind": "DiGraph",
            "nodes": [],
            "edges": [("a", "c"), ("b", "c"), ("c", "d")],
        },
        {
            "name": "multi_parallel",
            "kind": "MultiDiGraph",
            "nodes": [],
            "edges": [(0, 2), (0, 2), (1, 2), (2, 3)],
        },
        {"name": "dag450_profile_target", "kind": "DiGraph", "nodes": [], "edges": dag450_edges},
    ]


def _new_graph(module: Any, kind: str) -> Any:
    if kind == "DiGraph":
        return module.DiGraph()
    if kind == "MultiDiGraph":
        return module.MultiDiGraph()
    if kind == "Graph":
        return module.Graph()
    raise ValueError(f"unknown graph kind: {kind}")


def _build_graph(module: Any, spec: dict[str, Any]) -> Any:
    graph = _new_graph(module, spec["kind"])
    graph.add_nodes_from(spec["nodes"])
    graph.add_edges_from(spec["edges"])
    return graph


def _outcome(func: Callable[[], Any]) -> dict[str, Any]:
    try:
        return {"ok": True, "value": _stable(list(func()))}
    except BaseException as exc:  # noqa: BLE001 - exception class is evidence.
        return {
            "ok": False,
            "exception": type(exc).__name__,
            "message": str(exc),
        }


def _parity_records() -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for spec in _fixture_specs():
        fnx_graph = _build_graph(fnx, spec)
        nx_graph = _build_graph(nx, spec)
        fnx_result = _outcome(lambda graph=fnx_graph: fnx.topological_sort(graph))
        nx_result = _outcome(lambda graph=nx_graph: nx.topological_sort(graph))
        records.append(
            {
                "name": spec["name"],
                "kind": spec["kind"],
                "fnx": fnx_result,
                "networkx": nx_result,
                "match": fnx_result == nx_result,
            }
        )

    cycle_spec = {"kind": "DiGraph", "nodes": [], "edges": [(0, 1), (1, 0)]}
    undirected_spec = {"kind": "Graph", "nodes": [], "edges": [(0, 1)]}
    for name, spec in [("cycle_error", cycle_spec), ("undirected_error", undirected_spec)]:
        fnx_graph = _build_graph(fnx, spec)
        nx_graph = _build_graph(nx, spec)
        fnx_result = _outcome(lambda graph=fnx_graph: fnx.topological_sort(graph))
        nx_result = _outcome(lambda graph=nx_graph: nx.topological_sort(graph))
        records.append(
            {
                "name": name,
                "kind": spec["kind"],
                "fnx": fnx_result,
                "networkx": nx_result,
                "match": fnx_result == nx_result,
            }
        )
    return records


def _base_digraph(module: Any) -> Any:
    graph = module.DiGraph()
    graph.add_edges_from([(0, 2), (1, 2), (2, 3)])
    return graph


def _base_multidigraph(module: Any) -> Any:
    graph = module.MultiDiGraph()
    graph.add_edges_from([(0, 2), (1, 2), (2, 3)])
    return graph


def _mut_add_isolated(graph: Any) -> None:
    graph.add_node(9)


def _mut_add_forward_edge(graph: Any) -> None:
    graph.add_node(9)
    graph.add_edge(3, 9)


def _mut_add_cycle_edge(graph: Any) -> None:
    graph.add_edge(3, 0)


def _mut_remove_pending_node(graph: Any) -> None:
    graph.remove_node(2)


def _mut_remove_pending_edge(graph: Any) -> None:
    graph.remove_edge(2, 3)


def _mut_remove_yielded_node(graph: Any) -> None:
    graph.remove_node(0)


def _consume_after_mutation(
    module: Any,
    graph_factory: Callable[[Any], Any],
    mutator: Callable[[Any], None],
) -> dict[str, Any]:
    graph = graph_factory(module)
    iterator = module.topological_sort(graph)
    output: list[Any] = []
    try:
        output.append(next(iterator))
    except BaseException as exc:  # noqa: BLE001
        return {"output": _stable(output), "exception": type(exc).__name__, "message": str(exc)}
    try:
        mutator(graph)
    except BaseException as exc:  # noqa: BLE001
        return {
            "output": _stable(output),
            "exception": "mutate_" + type(exc).__name__,
            "message": str(exc),
        }
    try:
        output.extend(iterator)
        return {"output": _stable(output), "exception": None, "message": None}
    except BaseException as exc:  # noqa: BLE001
        return {"output": _stable(output), "exception": type(exc).__name__, "message": str(exc)}


def _mutation_records() -> list[dict[str, Any]]:
    mutators: list[tuple[str, Callable[[Any], None]]] = [
        ("add_isolated", _mut_add_isolated),
        ("add_forward_edge", _mut_add_forward_edge),
        ("add_cycle_edge", _mut_add_cycle_edge),
        ("remove_pending_node", _mut_remove_pending_node),
        ("remove_pending_edge", _mut_remove_pending_edge),
        ("remove_yielded_node", _mut_remove_yielded_node),
    ]
    graph_factories: list[tuple[str, Callable[[Any], Any]]] = [
        ("DiGraph", _base_digraph),
        ("MultiDiGraph", _base_multidigraph),
    ]
    records: list[dict[str, Any]] = []
    for graph_name, graph_factory in graph_factories:
        for mutator_name, mutator in mutators:
            records.append(
                {
                    "graph": graph_name,
                    "mutation": mutator_name,
                    "fnx": _consume_after_mutation(fnx, graph_factory, mutator),
                    "networkx": _consume_after_mutation(nx, graph_factory, mutator),
                }
            )
    return records


def _bench_graphs() -> tuple[Any, Any]:
    target = next(spec for spec in _fixture_specs() if spec["name"] == "dag450_profile_target")
    return _build_graph(fnx, target), _build_graph(nx, target)


def _time_calls(func: Callable[[], Any], iterations: int, rounds: int) -> dict[str, Any]:
    samples: list[float] = []
    for _ in range(3):
        func()
    for _ in range(rounds):
        start = time.perf_counter()
        for _ in range(iterations):
            func()
        elapsed = time.perf_counter() - start
        samples.append(elapsed / iterations)
    return {
        "iterations": iterations,
        "rounds": rounds,
        "samples_sec_per_call": samples,
        "best_sec_per_call": min(samples),
        "median_sec_per_call": statistics.median(samples),
    }


def _bench(iterations: int, rounds: int) -> dict[str, Any]:
    fnx_graph, nx_graph = _bench_graphs()
    fnx_bench = _time_calls(lambda: list(fnx.topological_sort(fnx_graph)), iterations, rounds)
    nx_bench = _time_calls(lambda: list(nx.topological_sort(nx_graph)), iterations, rounds)
    return {
        "scenario": "topological_sort_dag450",
        "fnx": fnx_bench,
        "networkx": nx_bench,
        "best_ratio_fnx_over_networkx": fnx_bench["best_sec_per_call"]
        / nx_bench["best_sec_per_call"],
        "median_ratio_fnx_over_networkx": fnx_bench["median_sec_per_call"]
        / nx_bench["median_sec_per_call"],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", default="baseline")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--expect-parity-sha")
    parser.add_argument("--expect-mutation-sha")
    parser.add_argument("--bench-only", action="store_true")
    parser.add_argument("--bench-iterations", type=int, default=500)
    parser.add_argument("--bench-rounds", type=int, default=9)
    args = parser.parse_args()

    if args.bench_only:
        print(json.dumps(_bench(args.bench_iterations, args.bench_rounds), sort_keys=True))
        return 0

    parity = _parity_records()
    mutations = _mutation_records()
    bench = _bench(args.bench_iterations, args.bench_rounds)
    parity_sha = _sha256(parity)
    mutation_sha = _sha256(mutations)
    report = {
        "bead": "br-r37-c1-04z53.62",
        "phase": args.phase,
        "python": {
            "franken_networkx": getattr(fnx, "__file__", None),
            "networkx": getattr(nx, "__file__", None),
            "networkx_version": getattr(nx, "__version__", None),
        },
        "proof": {
            "ordering_tie_breaking": "exact ordered topological_sort list equality",
            "floating_point_surface": "none",
            "rng_surface": "none",
            "parity_sha256": parity_sha,
            "mutation_sha256": mutation_sha,
            "all_parity_records_match": all(record["match"] for record in parity),
            "expected_parity_sha256": args.expect_parity_sha,
            "expected_mutation_sha256": args.expect_mutation_sha,
            "parity_sha_matches_expected": args.expect_parity_sha in (None, parity_sha),
            "mutation_sha_matches_expected": args.expect_mutation_sha in (None, mutation_sha),
        },
        "parity_records": parity,
        "mutation_records": mutations,
        "bench": bench,
    }
    if args.output is not None:
        args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    else:
        print(json.dumps(report, indent=2, sort_keys=True))

    if not report["proof"]["all_parity_records_match"]:
        return 1
    if not report["proof"]["parity_sha_matches_expected"]:
        return 1
    if not report["proof"]["mutation_sha_matches_expected"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
