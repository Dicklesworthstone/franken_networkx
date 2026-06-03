#!/usr/bin/env python3
"""Bench, profile, and golden harness for br-r37-c1-gl3nq."""

from __future__ import annotations

import argparse
import cProfile
import hashlib
import io
import json
import pstats
import statistics
import sys
import time
from collections.abc import Callable

import franken_networkx as fnx
import networkx as nx


def build_graph(module: object, n: int = 1800, p: float = 0.005) -> object:
    graph = module.gnp_random_graph(n, p, seed=23, directed=True)
    for i, (u, v) in enumerate(list(graph.edges())[:128]):
        graph[u][v]["w"] = i
    return graph


def edge_token(edge: tuple[object, object, dict[object, object]]) -> object:
    u, v, data = edge
    return [repr(u), repr(v), sorted((repr(k), repr(value)) for k, value in data.items())]


def graph_summary(module: object) -> dict[str, object]:
    graph = build_graph(module, n=36, p=0.15)
    view = module.to_edgelist(graph)
    first = next(iter(view))
    return {
        "type_name": type(view).__name__,
        "length": len(view),
        "edges": [edge_token(edge) for edge in view],
        "first_data_identity": first[2] is graph[first[0]][first[1]],
        "repr_prefix": repr(view).split("(", 1)[0],
    }


def case_builders(module: object) -> dict[str, Callable[[], object]]:
    graph = build_graph(module)
    return {
        "to_edgelist": lambda: module.to_edgelist(graph),
        "to_edgelist_list": lambda: list(module.to_edgelist(graph)),
    }


def bench(args: argparse.Namespace) -> None:
    builders = case_builders(fnx)
    selected = list(builders) if args.case == "all" else [args.case]
    for name in selected:
        times: list[float] = []
        size = 0
        for _ in range(args.repeat):
            start = time.perf_counter()
            result = builders[name]()
            elapsed = time.perf_counter() - start
            times.append(elapsed)
            size = len(result)
        print(
            json.dumps(
                {
                    "case": name,
                    "repeat": args.repeat,
                    "times_s": times,
                    "mean_s": statistics.fmean(times),
                    "median_s": statistics.median(times),
                    "min_s": min(times),
                    "max_s": max(times),
                    "size": size,
                },
                sort_keys=True,
            )
        )


def golden(args: argparse.Namespace) -> None:
    fnx_summary = graph_summary(fnx)
    nx_summary = graph_summary(nx)
    output = {
        "fnx": fnx_summary,
        "nx": nx_summary,
        "matches_nx_without_type": {
            key: fnx_summary[key] == nx_summary[key]
            for key in ("length", "edges", "first_data_identity")
        },
    }
    payload = json.dumps(output, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(payload.encode()).hexdigest()
    if args.sha_only:
        print(digest)
    else:
        print(json.dumps({"sha256": digest, "payload": output}, sort_keys=True, indent=2))


def profile(args: argparse.Namespace) -> None:
    builders = case_builders(fnx)
    profiler = cProfile.Profile()
    builder = builders[args.case]
    profiler.enable()
    for _ in range(args.repeat):
        builder()
    profiler.disable()
    stream = io.StringIO()
    stats = pstats.Stats(profiler, stream=stream).strip_dirs().sort_stats("cumtime")
    stats.print_stats(args.limit)
    sys.stdout.write(stream.getvalue())


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    bench_parser = sub.add_parser("bench")
    bench_parser.add_argument("--case", choices=["to_edgelist", "to_edgelist_list", "all"], default="all")
    bench_parser.add_argument("--repeat", type=int, default=11)
    bench_parser.set_defaults(func=bench)
    golden_parser = sub.add_parser("golden")
    golden_parser.add_argument("--sha-only", action="store_true")
    golden_parser.set_defaults(func=golden)
    profile_parser = sub.add_parser("profile")
    profile_parser.add_argument("--case", choices=["to_edgelist", "to_edgelist_list"], default="to_edgelist")
    profile_parser.add_argument("--repeat", type=int, default=20)
    profile_parser.add_argument("--limit", type=int, default=30)
    profile_parser.set_defaults(func=profile)
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
