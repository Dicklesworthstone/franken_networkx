#!/usr/bin/env python3
"""Current-head construction benchmarks for br-r37-c1-w1dm8."""

from __future__ import annotations

import argparse
import cProfile
import hashlib
import io
import json
import pstats
import statistics
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import franken_networkx as fnx
import networkx as nx


def _token(value: Any) -> str:
    return f"{type(value).__name__}:{value!r}"


def _digest(graph: Any) -> str:
    payload = {
        "nodes": [_token(node) for node in graph.nodes()],
        "edges": [
            [_token(u), _token(v), _token(key), sorted((str(k), repr(vv)) for k, vv in data.items())]
            for u, v, key, data in graph.edges(keys=True, data=True)
        ]
        if graph.is_multigraph()
        else [
            [_token(u), _token(v), sorted((str(k), repr(vv)) for k, vv in data.items())]
            for u, v, data in graph.edges(data=True)
        ],
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def build_add_nodes(module: Any, n: int) -> Any:
    graph = module.Graph()
    graph.add_nodes_from(range(n))
    return graph


def build_plain_edges(module: Any, n: int) -> Any:
    graph = module.Graph()
    graph.add_edges_from((i, i + 1) for i in range(n))
    return graph


def build_multigraph_int_keys(module: Any, n: int) -> Any:
    graph = module.MultiGraph()
    for i in range(n):
        graph.add_edge(i, i + 1, key=i)
    return graph


def build_multigraph_str_keys(module: Any, n: int) -> Any:
    graph = module.MultiGraph()
    for i in range(n):
        graph.add_edge(i, i + 1, key=str(i))
    return graph


CASES: dict[str, tuple[Callable[[Any, int], Any], int]] = {
    "add_nodes_int": (build_add_nodes, 100_000),
    "plain_edges_int": (build_plain_edges, 20_000),
    "multigraph_int_keys": (build_multigraph_int_keys, 50_000),
    "multigraph_str_keys": (build_multigraph_str_keys, 50_000),
}


def _time_case(module: Any, case: str, size: int, repeats: int) -> dict[str, Any]:
    builder, default_size = CASES[case]
    n = size or default_size
    samples: list[float] = []
    graph = None
    for _ in range(repeats):
        started = time.perf_counter()
        graph = builder(module, n)
        samples.append(time.perf_counter() - started)
    assert graph is not None
    return {
        "case": case,
        "size": n,
        "repeats": repeats,
        "mean_sec": statistics.fmean(samples),
        "median_sec": statistics.median(samples),
        "min_sec": min(samples),
        "max_sec": max(samples),
        "samples_sec": samples,
        "nodes": graph.number_of_nodes(),
        "edges": graph.number_of_edges(),
        "digest": _digest(graph),
    }


def bench(args: argparse.Namespace) -> None:
    selected = list(CASES) if args.case == "all" else [args.case]
    for case in selected:
        modules = (("fnx", fnx), ("nx", nx)) if args.impl == "both" else ((args.impl, fnx if args.impl == "fnx" else nx),)
        records = []
        for impl, module in modules:
            record = _time_case(module, case, args.size, args.repeats)
            record["impl"] = impl
            records.append(record)
        row: dict[str, Any] = {"case": case, "records": records}
        if len(records) == 2:
            fnx_record, nx_record = records
            row["fnx_over_nx"] = fnx_record["mean_sec"] / nx_record["mean_sec"]
            row["digests_match"] = fnx_record["digest"] == nx_record["digest"]
        print(json.dumps(row, sort_keys=True, separators=(",", ":")), flush=True)


def profile(args: argparse.Namespace) -> None:
    module = fnx if args.impl == "fnx" else nx
    profiler = cProfile.Profile()
    profiler.enable()
    record = _time_case(module, args.case, args.size, args.repeats)
    profiler.disable()
    stream = io.StringIO()
    pstats.Stats(profiler, stream=stream).strip_dirs().sort_stats("cumtime").print_stats(args.limit)
    Path(args.output).write_text(stream.getvalue(), encoding="utf-8")
    record["impl"] = args.impl
    record["profile_output"] = args.output
    print(json.dumps(record, sort_keys=True, separators=(",", ":")), flush=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="cmd", required=True)
    bench_parser = subparsers.add_parser("bench")
    bench_parser.add_argument("--case", choices=[*CASES, "all"], default="all")
    bench_parser.add_argument("--impl", choices=("fnx", "nx", "both"), default="both")
    bench_parser.add_argument("--size", type=int, default=0)
    bench_parser.add_argument("--repeats", type=int, default=7)
    bench_parser.set_defaults(func=bench)
    profile_parser = subparsers.add_parser("profile")
    profile_parser.add_argument("--case", choices=CASES, required=True)
    profile_parser.add_argument("--impl", choices=("fnx", "nx"), default="fnx")
    profile_parser.add_argument("--size", type=int, default=0)
    profile_parser.add_argument("--repeats", type=int, default=5)
    profile_parser.add_argument("--limit", type=int, default=60)
    profile_parser.add_argument("--output", required=True)
    profile_parser.set_defaults(func=profile)
    args = parser.parse_args()
    args.func(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
