#!/usr/bin/env python3
"""Baseline/profiling harness for br-r37-c1-f0zo8.

This file is an artifact-only harness. It does not modify production code.
"""

from __future__ import annotations

import argparse
import cProfile
import json
import pstats
import statistics
import sys
import time
from pathlib import Path


def _import_fresh_modules():
    import franken_networkx as fnx
    import networkx as nx

    return fnx, nx


def build_graph(module, graph_name: str, degree: int, keys_per_neighbor: int):
    graph = getattr(module, graph_name)()
    for nbr in range(1, degree + 1):
        for key in range(keys_per_neighbor):
            graph.add_edge(
                0,
                nbr,
                key=key,
                weight=(nbr * 1000) + key,
                label=f"edge-{nbr}-{key}",
            )
    return graph


def choose_neighbor(degree: int) -> int:
    return max(1, degree // 2)


def workload(graph, graph_name: str, mode: str, loops: int, degree: int) -> int:
    target = choose_neighbor(degree)
    total = 0
    if mode == "gu":
        for _ in range(loops):
            view = graph[0]
            total += len(view)
        return total
    if mode == "guv":
        for _ in range(loops):
            keydict = graph[0][target]
            total += len(keydict)
        return total
    if mode == "guv_attr":
        for _ in range(loops):
            total += graph[0][target][0]["weight"]
        return total
    if mode == "materialize_outer":
        for _ in range(loops):
            view = graph[0]
            total += sum(len(keydict) for keydict in view.values())
        return total
    if mode == "iterate_items":
        for _ in range(loops):
            for nbr, keydict in graph[0].items():
                total += nbr
                total += len(keydict)
        return total
    if mode == "mutate_attr":
        for i in range(loops):
            attrs = graph[0][target][0]
            attrs["seen"] = i
            total += attrs["seen"]
        return total
    raise ValueError(f"unknown mode: {mode}")


def time_mode(module_name: str, graph_name: str, mode: str, degree: int, keys: int, loops: int, rounds: int):
    fnx, nx = _import_fresh_modules()
    module = fnx if module_name == "fnx" else nx
    graph = build_graph(module, graph_name, degree, keys)
    samples = []
    checksum = None
    for _ in range(rounds):
        started = time.perf_counter_ns()
        checksum = workload(graph, graph_name, mode, loops, degree)
        elapsed = time.perf_counter_ns() - started
        samples.append(elapsed / loops)
    return {
        "module": module_name,
        "graph": graph_name,
        "mode": mode,
        "degree": degree,
        "keys_per_neighbor": keys,
        "loops": loops,
        "rounds": rounds,
        "checksum": checksum,
        "ns_per_loop_min": min(samples),
        "ns_per_loop_median": statistics.median(samples),
        "ns_per_loop_mean": statistics.fmean(samples),
        "ns_per_loop_max": max(samples),
    }


def run_sweep(args: argparse.Namespace) -> int:
    rows = []
    for module_name in args.modules:
        for graph_name in args.graphs:
            for mode in args.modes:
                row = time_mode(
                    module_name,
                    graph_name,
                    mode,
                    args.degree,
                    args.keys_per_neighbor,
                    args.loops,
                    args.rounds,
                )
                rows.append(row)
                print(json.dumps(row, sort_keys=True), flush=True)
    if args.output:
        path = Path(args.output)
        with path.open("w", encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps(row, sort_keys=True) + "\n")
    return 0


def run_scale(args: argparse.Namespace) -> int:
    rows = []
    for degree in args.degrees:
        for module_name in args.modules:
            for graph_name in args.graphs:
                for mode in args.modes:
                    row = time_mode(
                        module_name,
                        graph_name,
                        mode,
                        degree,
                        args.keys_per_neighbor,
                        args.loops,
                        args.rounds,
                    )
                    rows.append(row)
                    print(json.dumps(row, sort_keys=True), flush=True)
    if args.output:
        path = Path(args.output)
        with path.open("w", encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps(row, sort_keys=True) + "\n")
    return 0


def run_one(args: argparse.Namespace) -> int:
    fnx, nx = _import_fresh_modules()
    module = fnx if args.module == "fnx" else nx
    graph = build_graph(module, args.graph, args.degree, args.keys_per_neighbor)
    result = workload(graph, args.graph, args.mode, args.loops, args.degree)
    print(
        json.dumps(
            {
                "module": args.module,
                "graph": args.graph,
                "mode": args.mode,
                "degree": args.degree,
                "keys_per_neighbor": args.keys_per_neighbor,
                "loops": args.loops,
                "checksum": result,
            },
            sort_keys=True,
        )
    )
    return 0


def run_profile(args: argparse.Namespace) -> int:
    fnx, nx = _import_fresh_modules()
    module = fnx if args.module == "fnx" else nx
    graph = build_graph(module, args.graph, args.degree, args.keys_per_neighbor)
    profiler = cProfile.Profile()
    profiler.enable()
    result = workload(graph, args.graph, args.mode, args.loops, args.degree)
    profiler.disable()
    stats_path = Path(args.output)
    text_path = Path(args.text_output)
    profiler.dump_stats(stats_path)
    with text_path.open("w", encoding="utf-8") as handle:
        handle.write(
            json.dumps(
                {
                    "module": args.module,
                    "graph": args.graph,
                    "mode": args.mode,
                    "degree": args.degree,
                    "keys_per_neighbor": args.keys_per_neighbor,
                    "loops": args.loops,
                    "checksum": result,
                },
                sort_keys=True,
            )
            + "\n\n"
        )
        stats = pstats.Stats(profiler, stream=handle).strip_dirs().sort_stats("tottime")
        stats.print_stats(40)
    print(
        json.dumps(
            {
                "profile_stats": str(stats_path),
                "profile_text": str(text_path),
                "checksum": result,
            },
            sort_keys=True,
        )
    )
    return 0


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    common_modes = ["gu", "guv", "guv_attr", "materialize_outer", "iterate_items", "mutate_attr"]

    sweep = subparsers.add_parser("sweep")
    sweep.add_argument("--modules", nargs="+", default=["fnx", "nx"], choices=["fnx", "nx"])
    sweep.add_argument("--graphs", nargs="+", default=["MultiGraph", "MultiDiGraph"], choices=["MultiGraph", "MultiDiGraph"])
    sweep.add_argument("--modes", nargs="+", default=common_modes, choices=common_modes)
    sweep.add_argument("--degree", type=int, default=2000)
    sweep.add_argument("--keys-per-neighbor", type=int, default=4)
    sweep.add_argument("--loops", type=int, default=2000)
    sweep.add_argument("--rounds", type=int, default=5)
    sweep.add_argument("--output")
    sweep.set_defaults(func=run_sweep)

    scale = subparsers.add_parser("scale")
    scale.add_argument("--modules", nargs="+", default=["fnx"], choices=["fnx", "nx"])
    scale.add_argument("--graphs", nargs="+", default=["MultiGraph", "MultiDiGraph"], choices=["MultiGraph", "MultiDiGraph"])
    scale.add_argument("--modes", nargs="+", default=["gu", "guv"], choices=common_modes)
    scale.add_argument("--degrees", nargs="+", type=int, default=[50, 100, 250, 500])
    scale.add_argument("--keys-per-neighbor", type=int, default=4)
    scale.add_argument("--loops", type=int, default=50)
    scale.add_argument("--rounds", type=int, default=3)
    scale.add_argument("--output")
    scale.set_defaults(func=run_scale)

    one = subparsers.add_parser("one")
    one.add_argument("--module", choices=["fnx", "nx"], default="fnx")
    one.add_argument("--graph", choices=["MultiGraph", "MultiDiGraph"], required=True)
    one.add_argument("--mode", choices=common_modes, required=True)
    one.add_argument("--degree", type=int, default=2000)
    one.add_argument("--keys-per-neighbor", type=int, default=4)
    one.add_argument("--loops", type=int, default=10000)
    one.set_defaults(func=run_one)

    profile = subparsers.add_parser("profile")
    profile.add_argument("--module", choices=["fnx", "nx"], default="fnx")
    profile.add_argument("--graph", choices=["MultiGraph", "MultiDiGraph"], required=True)
    profile.add_argument("--mode", choices=common_modes, required=True)
    profile.add_argument("--degree", type=int, default=2000)
    profile.add_argument("--keys-per-neighbor", type=int, default=4)
    profile.add_argument("--loops", type=int, default=5000)
    profile.add_argument("--output", required=True)
    profile.add_argument("--text-output", required=True)
    profile.set_defaults(func=run_profile)

    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
