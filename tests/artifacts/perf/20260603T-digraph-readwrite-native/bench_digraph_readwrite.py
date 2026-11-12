#!/usr/bin/env python3
"""Bench, profile, and golden harness for br-r37-c1-nocb2."""

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


def build_graph(module: object, n: int = 1200, p: float = 0.006) -> object:
    graph = module.gnp_random_graph(n, p, seed=17, directed=True)
    for i, (u, v) in enumerate(list(graph.edges())[:64]):
        graph[u][v]["w"] = i
    return graph


def normalize_value(value: object) -> object:
    if isinstance(value, dict):
        return sorted((repr(k), repr(v)) for k, v in value.items())
    if isinstance(value, list):
        return [repr(item) for item in value]
    return repr(value)


def normalize_mapping(mapping: dict[object, object]) -> list[tuple[str, object]]:
    return [(repr(key), normalize_value(value)) for key, value in mapping.items()]


def graph_summary(module: object) -> dict[str, object]:
    graph = build_graph(module, n=32, p=0.12)
    dicts = module.to_dict_of_dicts(graph)
    lists = module.to_dict_of_lists(graph)
    first_edge = next(iter(graph.edges()))
    return {
        "nodes": [repr(node) for node in graph.nodes()],
        "edges": [(repr(u), repr(v), sorted(graph[u][v].items())) for u, v in graph.edges()],
        "dicts": [(repr(u), normalize_mapping(vs)) for u, vs in dicts.items()],
        "lists": [(repr(u), [repr(v) for v in vs]) for u, vs in lists.items()],
        "edge_dict_identity": dicts[first_edge[0]][first_edge[1]] is graph[first_edge[0]][first_edge[1]],
    }


def slow_to_dict_of_dicts(graph: object) -> dict[object, object]:
    nodelist = list(graph.nodes())
    nodeset = set(nodelist)
    result: dict[object, object] = {}
    for u in nodelist:
        result[u] = {}
        for v, data in graph[u].items():
            if v in nodeset:
                result[u][v] = data
    return result


def slow_to_dict_of_lists(graph: object) -> dict[object, list[object]]:
    nodelist = graph
    return {n: [nb for nb in graph.neighbors(n) if nb in nodelist] for n in nodelist}


def case_builders(module: object, impl: str = "fast") -> dict[str, Callable[[], object]]:
    graph = build_graph(module)
    if impl == "slow":
        return {
            "dicts": lambda: slow_to_dict_of_dicts(graph),
            "lists": lambda: slow_to_dict_of_lists(graph),
        }
    return {
        "dicts": lambda: module.to_dict_of_dicts(graph),
        "lists": lambda: module.to_dict_of_lists(graph),
    }


def bench(args: argparse.Namespace) -> None:
    builders = case_builders(fnx, args.impl)
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
                    "impl": args.impl,
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
    output = {"fnx": graph_summary(fnx), "nx": graph_summary(nx)}
    output["matches_nx"] = {
        key: output["fnx"][key] == output["nx"][key]
        for key in ("nodes", "edges", "dicts", "lists", "edge_dict_identity")
    }
    payload = json.dumps(output, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(payload.encode()).hexdigest()
    if args.sha_only:
        print(digest)
    else:
        print(json.dumps({"sha256": digest, "payload": output}, sort_keys=True, indent=2))


def profile(args: argparse.Namespace) -> None:
    builders = case_builders(fnx, args.impl)
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
    bench_parser.add_argument("--case", choices=["dicts", "lists", "all"], default="all")
    bench_parser.add_argument("--impl", choices=["fast", "slow"], default="fast")
    bench_parser.add_argument("--repeat", type=int, default=11)
    bench_parser.set_defaults(func=bench)
    golden_parser = sub.add_parser("golden")
    golden_parser.add_argument("--sha-only", action="store_true")
    golden_parser.set_defaults(func=golden)
    profile_parser = sub.add_parser("profile")
    profile_parser.add_argument("--case", choices=["dicts", "lists"], default="dicts")
    profile_parser.add_argument("--impl", choices=["fast", "slow"], default="fast")
    profile_parser.add_argument("--repeat", type=int, default=20)
    profile_parser.add_argument("--limit", type=int, default=30)
    profile_parser.set_defaults(func=profile)
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
