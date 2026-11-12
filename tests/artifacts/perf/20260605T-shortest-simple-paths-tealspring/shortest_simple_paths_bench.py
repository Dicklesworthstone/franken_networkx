#!/usr/bin/env python3
"""Benchmark/proof harness for br-r37-c1-1bcb7.

The candidate route uses NetworkX's own shortest_simple_paths generator directly
on a FrankenNetworkX graph object. That avoids full fnx->nx conversion while
preserving NetworkX's Yen implementation, ordering, laziness, exceptions, and
weight handling.
"""

from __future__ import annotations

import argparse
import cProfile
import hashlib
import itertools
import json
import pstats
import sys
import time

import networkx as nx
import networkx.algorithms.simple_paths as nx_simple_paths
import franken_networkx as fnx


def _path_graph(lib, n: int):
    return lib.path_graph(n)


def _cycle_graph(lib, n: int):
    return lib.cycle_graph(n)


def _weighted_diamond(lib):
    graph = lib.Graph()
    for u, v, w in (
        (0, 1, 1.0),
        (1, 3, 1.0),
        (0, 2, 1.0),
        (2, 3, 2.0),
        (0, 3, 5.0),
    ):
        graph.add_edge(u, v, weight=w)
    return graph


def _gnp_graph(lib, n: int, p: float, seed: int):
    graph = lib.gnp_random_graph(n, p, seed)
    if not lib.has_path(graph, 0, n - 1):
        graph.add_edge(0, n - 1)
    return graph


def build_graph(impl: str, case: str):
    lib = nx if impl == "nx" else fnx
    if case == "path_2000_first1":
        return _path_graph(lib, 2000), 0, 1999, None, 1
    if case == "cycle_2000_first2":
        return _cycle_graph(lib, 2000), 0, 1000, None, 2
    if case == "weighted_diamond_all":
        return _weighted_diamond(lib), 0, 3, "weight", 8
    if case == "gnp_600_first3":
        return _gnp_graph(lib, 600, 0.01, 7), 0, 599, None, 3
    raise ValueError(f"unknown case: {case}")


CASES = (
    "path_2000_first1",
    "cycle_2000_first2",
    "weighted_diamond_all",
    "gnp_600_first3",
)


def shortest_simple_paths(impl: str, graph, source, target, weight):
    if impl == "fnx":
        return fnx.shortest_simple_paths(graph, source, target, weight=weight)
    if impl == "nx":
        return nx.shortest_simple_paths(graph, source, target, weight=weight)
    if impl == "direct":
        if graph.is_multigraph():
            return fnx.shortest_simple_paths(graph, source, target, weight=weight)
        return nx_simple_paths.shortest_simple_paths.orig_func(
            graph, source, target, weight=weight
        )
    raise ValueError(f"unknown impl: {impl}")


def take_paths(impl: str, case: str):
    graph, source, target, weight, limit = build_graph(impl, case)
    return list(
        itertools.islice(
            shortest_simple_paths(impl, graph, source, target, weight),
            limit,
        )
    )


def exception_row(impl: str, graph_kind: str, source, target, weight=None):
    lib = nx if impl == "nx" else fnx
    if graph_kind == "missing_source":
        graph = lib.path_graph(4)
        source = 99
    elif graph_kind == "missing_target":
        graph = lib.path_graph(4)
        target = 99
    elif graph_kind == "no_path":
        graph = lib.Graph()
        graph.add_node(0)
        graph.add_node(1)
    elif graph_kind == "multigraph":
        graph = lib.MultiGraph()
        graph.add_edge(0, 1)
    else:
        raise ValueError(graph_kind)

    try:
        list(shortest_simple_paths(impl, graph, source, target, weight))
    except Exception as exc:  # noqa: BLE001 - proof artifact records public shape.
        return {
            "kind": graph_kind,
            "type": type(exc).__name__,
            "message": str(exc),
        }
    return {"kind": graph_kind, "type": None, "message": None}


def canonical_rows(impl: str):
    rows = []
    for case in CASES:
        rows.append({"case": case, "paths": take_paths(impl, case)})
    rows.extend(
        exception_row(impl, kind, 0, 3)
        for kind in ("missing_source", "missing_target", "no_path", "multigraph")
    )
    return rows


def golden(args: argparse.Namespace) -> int:
    rows = {"fnx": canonical_rows("fnx"), "direct": canonical_rows("direct")}
    text = json.dumps(rows, sort_keys=True, separators=(",", ":"))
    if args.output:
        with open(args.output, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.write("\n")
    print(hashlib.sha256(text.encode("utf-8")).hexdigest())
    return 0


def compare(args: argparse.Namespace) -> int:
    expected = canonical_rows("fnx")
    candidate = canonical_rows("direct")
    if expected != candidate:
        print(json.dumps({"expected": expected, "candidate": candidate}, indent=2))
        return 1
    print("compare ok")
    return 0


def bench(args: argparse.Namespace) -> int:
    graph, source, target, weight, limit = build_graph(args.impl, args.case)
    start = time.perf_counter()
    total_paths = 0
    total_nodes = 0
    for _ in range(args.loops):
        paths = list(
            itertools.islice(
                shortest_simple_paths(args.impl, graph, source, target, weight),
                limit,
            )
        )
        total_paths += len(paths)
        total_nodes += sum(len(path) for path in paths)
    elapsed = time.perf_counter() - start
    print(
        json.dumps(
            {
                "case": args.case,
                "impl": args.impl,
                "loops": args.loops,
                "paths": total_paths,
                "path_nodes": total_nodes,
                "seconds": elapsed,
            },
            sort_keys=True,
        )
    )
    return 0


def profile(args: argparse.Namespace) -> int:
    profiler = cProfile.Profile()
    profiler.enable()
    bench(args)
    profiler.disable()
    stats = pstats.Stats(profiler, stream=sys.stdout).sort_stats("cumulative")
    stats.print_stats(args.limit)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)

    golden_parser = sub.add_parser("golden")
    golden_parser.add_argument("--output")
    golden_parser.set_defaults(func=golden)

    compare_parser = sub.add_parser("compare")
    compare_parser.set_defaults(func=compare)

    bench_parser = sub.add_parser("bench")
    bench_parser.add_argument("--impl", choices=("fnx", "nx", "direct"), required=True)
    bench_parser.add_argument("--case", choices=CASES, required=True)
    bench_parser.add_argument("--loops", type=int, default=10)
    bench_parser.set_defaults(func=bench)

    profile_parser = sub.add_parser("profile")
    profile_parser.add_argument("--impl", choices=("fnx", "nx", "direct"), required=True)
    profile_parser.add_argument("--case", choices=CASES, required=True)
    profile_parser.add_argument("--loops", type=int, default=10)
    profile_parser.add_argument("--limit", type=int, default=40)
    profile_parser.set_defaults(func=profile)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
