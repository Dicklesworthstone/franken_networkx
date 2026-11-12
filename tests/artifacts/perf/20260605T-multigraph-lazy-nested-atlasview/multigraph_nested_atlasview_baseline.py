#!/usr/bin/env python3
"""Baseline/profile/golden harness for br-r37-c1-f0zo8.

This pass intentionally records current eager nested adjacency behavior for
MultiGraph and MultiDiGraph. It does not exercise or require source changes.
"""

from __future__ import annotations

import argparse
import cProfile
import hashlib
import json
import pstats
import statistics
import sys
import time
from pathlib import Path
from typing import Any

import franken_networkx as fnx
import networkx as nx


SOURCE = 0
TARGET = 1
DEFAULT_NEIGHBORS = 720
DEFAULT_PARALLEL = 16


def build_workload(module: Any, graph_kind: str, neighbors: int, parallel: int) -> Any:
    graph_type = module.MultiGraph if graph_kind == "multigraph" else module.MultiDiGraph
    graph = graph_type()
    graph.add_nodes_from(range(neighbors + 1))
    for neighbor in range(1, neighbors + 1):
        for key in range(parallel):
            graph.add_edge(
                SOURCE,
                neighbor,
                key=key,
                weight=(neighbor * 131 + key * 17) % 997,
                tag=f"e{neighbor}:{key}",
            )
    return graph


def build_golden_graph(module: Any, graph_kind: str) -> Any:
    graph_type = module.MultiGraph if graph_kind == "multigraph" else module.MultiDiGraph
    graph = graph_type()
    graph.add_node("isolated")
    graph.add_edge("hub", "alpha", key=2, weight=7, tag="first")
    graph.add_edge("hub", "alpha", key="k0", weight=11, tag="second")
    graph.add_edge("hub", "beta", key=0, weight=13, tag="third")
    graph.add_edge("hub", "gamma", key="g", weight=17, tag="fourth")
    if graph_kind == "multigraph":
        graph.add_edge("omega", "hub", key="reverse", weight=19, tag="fifth")
    else:
        graph.add_edge("omega", "hub", key="incoming", weight=19, tag="fifth")
    return graph


def stable_key(value: Any) -> dict[str, str]:
    return {
        "type": type(value).__name__,
        "repr": repr(value),
        "str": str(value),
    }


def exception_signature(fn: Any) -> dict[str, Any]:
    try:
        fn()
    except Exception as exc:  # noqa: BLE001 - artifact records exact public shape.
        return {
            "type": type(exc).__name__,
            "args": [repr(arg) for arg in getattr(exc, "args", ())],
            "str": str(exc),
            "repr": repr(exc),
        }
    return {"type": "NO_EXCEPTION"}


def attr_signature(attrs: Any) -> list[list[Any]]:
    return [[stable_key(key), value] for key, value in attrs.items()]


def keydict_signature(keydict: Any) -> list[list[Any]]:
    return [[stable_key(key), attr_signature(attrs)] for key, attrs in keydict.items()]


def row_signature(row: Any) -> list[list[Any]]:
    return [[stable_key(neighbor), keydict_signature(keydict)] for neighbor, keydict in row.items()]


def materialized_value_shape(mapping: Any) -> list[list[Any]]:
    return [
        [
            stable_key(key),
            {
                "type": type(value).__name__,
                "repr_prefix": repr(value)[:160],
                "keys": [stable_key(inner_key) for inner_key in value.keys()],
            },
        ]
        for key, value in mapping.items()
    ]


def golden_for(module: Any, module_name: str, graph_kind: str) -> dict[str, Any]:
    graph = build_golden_graph(module, graph_kind)
    row = graph["hub"]
    alpha = row["alpha"]
    alpha_first_attrs = alpha[2]
    alpha_first_attrs["via_view"] = module_name
    graph.add_edge("hub", "alpha", key="late", weight=23, tag="late")
    if graph_kind == "multigraph":
        graph.add_edge("hub", "delta", key=0, weight=29, tag="late-neighbor")
    else:
        graph.add_edge("hub", "delta", key=0, weight=29, tag="late-successor")

    copy_value = row.copy()
    dict_value = dict(row)
    row_after = graph["hub"]
    alpha_after = row_after["alpha"]

    return {
        "module": module_name,
        "graph_kind": graph_kind,
        "row_type": f"{type(row).__module__}.{type(row).__name__}",
        "inner_type": f"{type(alpha).__module__}.{type(alpha).__name__}",
        "row_repr": repr(row),
        "inner_repr": repr(alpha),
        "neighbor_order_before": [stable_key(key) for key in row],
        "edge_key_order_before": [stable_key(key) for key in alpha],
        "neighbor_order_after_mutation": [stable_key(key) for key in row_after],
        "edge_key_order_after_mutation": [stable_key(key) for key in alpha_after],
        "row_signature_after_mutation": row_signature(row_after),
        "view_attr_mutation_visible": graph["hub"]["alpha"][2].get("via_view"),
        "copy_type": f"{type(copy_value).__module__}.{type(copy_value).__name__}",
        "copy_shape": materialized_value_shape(copy_value),
        "dict_type": f"{type(dict_value).__module__}.{type(dict_value).__name__}",
        "dict_shape": materialized_value_shape(dict_value),
        "missing_node": exception_signature(lambda: graph["missing-node"]),
        "missing_neighbor": exception_signature(lambda: graph["hub"]["missing-neighbor"]),
        "missing_key": exception_signature(lambda: graph["hub"]["alpha"]["missing-key"]),
    }


def golden() -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    for graph_kind in ("multigraph", "multidigraph"):
        records.append(golden_for(fnx, "franken_networkx", graph_kind))
        records.append(golden_for(nx, "networkx", graph_kind))
    payload = {
        "bead": "br-r37-c1-f0zo8",
        "purpose": "current eager nested adjacency golden before lazy MultiGraph/MultiDiGraph views",
        "python": sys.version,
        "franken_networkx_file": getattr(fnx, "__file__", None),
        "networkx_version": getattr(nx, "__version__", None),
        "records": records,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return {"digest": hashlib.sha256(encoded).hexdigest(), "payload": payload}


def operation(graph: Any, name: str) -> Any:
    if name == "gu":
        return graph[SOURCE]
    if name == "guv":
        return graph[SOURCE][TARGET]
    raise ValueError(f"unknown operation: {name}")


def run_loops(graph: Any, name: str, loops: int) -> int:
    observed = 0
    for _ in range(loops):
        value = operation(graph, name)
        observed += len(value)
    return observed


def benchmark(args: argparse.Namespace) -> dict[str, Any]:
    module = fnx if args.library == "fnx" else nx
    graph = build_workload(module, args.graph, args.neighbors, args.parallel)
    samples: list[float] = []
    observed = 0
    for _ in range(args.samples):
        start = time.perf_counter_ns()
        observed = run_loops(graph, args.operation, args.loops)
        elapsed = time.perf_counter_ns() - start
        samples.append(elapsed / args.loops / 1_000_000)
    samples_sorted = sorted(samples)
    return {
        "bead": "br-r37-c1-f0zo8",
        "library": args.library,
        "graph": args.graph,
        "operation": args.operation,
        "neighbors": args.neighbors,
        "parallel_edges_per_neighbor": args.parallel,
        "loops_per_sample": args.loops,
        "samples": args.samples,
        "observed_len_accumulator": observed,
        "time_ms_per_op": {
            "min": min(samples),
            "mean": statistics.fmean(samples),
            "median": statistics.median(samples),
            "p95": samples_sorted[min(len(samples_sorted) - 1, int(len(samples_sorted) * 0.95))],
            "max": max(samples),
            "samples": samples,
        },
    }


def profile(args: argparse.Namespace) -> None:
    module = fnx if args.library == "fnx" else nx
    graph = build_workload(module, args.graph, args.neighbors, args.parallel)
    profiler = cProfile.Profile()
    profiler.enable()
    observed = run_loops(graph, args.operation, args.loops)
    profiler.disable()
    print(
        json.dumps(
            {
                "bead": "br-r37-c1-f0zo8",
                "profile": {
                    "library": args.library,
                    "graph": args.graph,
                    "operation": args.operation,
                    "neighbors": args.neighbors,
                    "parallel_edges_per_neighbor": args.parallel,
                    "loops": args.loops,
                    "observed_len_accumulator": observed,
                },
            },
            sort_keys=True,
        )
    )
    stats = pstats.Stats(profiler, stream=sys.stdout).sort_stats("cumulative")
    stats.print_stats(args.limit)


def write_json(path: str | None, data: Any) -> None:
    if path is None:
        print(json.dumps(data, indent=2, sort_keys=True))
        return
    Path(path).write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="mode", required=True)

    bench_parser = subparsers.add_parser("benchmark")
    bench_parser.add_argument("--library", choices=("fnx", "nx"), required=True)
    bench_parser.add_argument("--graph", choices=("multigraph", "multidigraph"), required=True)
    bench_parser.add_argument("--operation", choices=("gu", "guv"), required=True)
    bench_parser.add_argument("--neighbors", type=int, default=DEFAULT_NEIGHBORS)
    bench_parser.add_argument("--parallel", type=int, default=DEFAULT_PARALLEL)
    bench_parser.add_argument("--loops", type=int, default=40)
    bench_parser.add_argument("--samples", type=int, default=11)
    bench_parser.add_argument("--output")

    profile_parser = subparsers.add_parser("profile")
    profile_parser.add_argument("--library", choices=("fnx", "nx"), required=True)
    profile_parser.add_argument("--graph", choices=("multigraph", "multidigraph"), required=True)
    profile_parser.add_argument("--operation", choices=("gu", "guv"), required=True)
    profile_parser.add_argument("--neighbors", type=int, default=DEFAULT_NEIGHBORS)
    profile_parser.add_argument("--parallel", type=int, default=DEFAULT_PARALLEL)
    profile_parser.add_argument("--loops", type=int, default=80)
    profile_parser.add_argument("--limit", type=int, default=30)

    golden_parser = subparsers.add_parser("golden")
    golden_parser.add_argument("--output")

    args = parser.parse_args()
    if args.mode == "benchmark":
        write_json(args.output, benchmark(args))
    elif args.mode == "profile":
        profile(args)
    else:
        write_json(args.output, golden())


if __name__ == "__main__":
    main()
