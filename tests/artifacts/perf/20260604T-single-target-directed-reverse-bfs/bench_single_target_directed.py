#!/usr/bin/env python3
"""Directed single-target shortest-path-length benchmark for br-r37-c1-a0nl0."""

from __future__ import annotations

import argparse
import cProfile
import hashlib
import json
import pstats
import statistics
import sys
import time
from typing import Any

import franken_networkx as fnx
import networkx as nx


def stable(value: Any) -> Any:
    if isinstance(value, dict):
        return [[stable(key), stable(item)] for key, item in value.items()]
    if isinstance(value, (list, tuple)):
        return [stable(item) for item in value]
    return f"{type(value).__name__}:{value!r}"


def digest(value: Any) -> str:
    payload = json.dumps(stable(value), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def build_graph(module: Any, n: int) -> Any:
    graph = module.DiGraph()
    graph.add_edges_from((i, i + 1) for i in range(n - 1))
    graph.add_edges_from((i, i + 3) for i in range(n - 3))
    graph.add_edges_from((i, i + 7) for i in range(n - 7))
    return graph


def run_case(module: Any, graph: Any, target: int, cutoff: int | None) -> dict[Any, int]:
    return dict(module.single_target_shortest_path_length(graph, target, cutoff=cutoff))


def bench(args: argparse.Namespace) -> int:
    records = []
    impls = (("fnx", fnx), ("nx", nx)) if args.impl == "both" else ((args.impl, fnx if args.impl == "fnx" else nx),)
    for name, module in impls:
        graph = build_graph(module, args.size)
        samples = []
        value = None
        for _ in range(args.repeats):
            start = time.perf_counter()
            value = run_case(module, graph, args.target, args.cutoff)
            samples.append(time.perf_counter() - start)
        assert value is not None
        records.append(
            {
                "impl": name,
                "size": args.size,
                "target": args.target,
                "cutoff": args.cutoff,
                "repeats": args.repeats,
                "mean_sec": statistics.fmean(samples),
                "median_sec": statistics.median(samples),
                "min_sec": min(samples),
                "max_sec": max(samples),
                "samples_sec": samples,
                "digest": digest(value),
                "item_count": len(value),
            }
        )
    fnx_record = next((record for record in records if record["impl"] == "fnx"), None)
    nx_record = next((record for record in records if record["impl"] == "nx"), None)
    print(
        json.dumps(
            {
                "case": "directed_single_target_shortest_path_length",
                "records": records,
                "fnx_over_nx": (
                    fnx_record["mean_sec"] / nx_record["mean_sec"]
                    if fnx_record is not None and nx_record is not None
                    else None
                ),
                "digests_match": (
                    fnx_record["digest"] == nx_record["digest"]
                    if fnx_record is not None and nx_record is not None
                    else None
                ),
            },
            sort_keys=True,
            separators=(",", ":"),
        )
    )
    return 0


def profile(args: argparse.Namespace) -> int:
    if args.impl == "both":
        raise ValueError("--mode profile requires --impl fnx or --impl nx")
    module = fnx if args.impl == "fnx" else nx
    graph = build_graph(module, args.size)
    profiler = cProfile.Profile()

    def repeated() -> None:
        for _ in range(args.repeats):
            run_case(module, graph, args.target, args.cutoff)

    profiler.enable()
    repeated()
    profiler.disable()
    stats = pstats.Stats(profiler, stream=sys.stderr).sort_stats("cumulative")
    stats.print_stats(args.profile_limit)
    value = run_case(module, graph, args.target, args.cutoff)
    print(
        json.dumps(
            {
                "impl": args.impl,
                "size": args.size,
                "target": args.target,
                "cutoff": args.cutoff,
                "repeats": args.repeats,
                "digest": digest(value),
                "item_count": len(value),
            },
            sort_keys=True,
            separators=(",", ":"),
        )
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["bench", "profile"], default="bench")
    parser.add_argument("--impl", choices=["both", "fnx", "nx"], default="both")
    parser.add_argument("--size", type=int, default=5_000)
    parser.add_argument("--target", type=int, default=4_999)
    parser.add_argument("--cutoff", type=int, default=None)
    parser.add_argument("--repeats", type=int, default=30)
    parser.add_argument("--profile-limit", type=int, default=30)
    args = parser.parse_args()
    if args.mode == "profile":
        return profile(args)
    return bench(args)


if __name__ == "__main__":
    raise SystemExit(main())
