#!/usr/bin/env python3
"""Bench and golden harness for br-r37-c1-71x9k.

Targets the profile-backed sparse-generator construction path:
plain two-tuple Graph.add_edges_from calls in franken_networkx.
"""

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


def raw_int_edges(n: int) -> list[tuple[int, int]]:
    return [(i, i + 1) for i in range(n)]


def raw_tuple_edges(rows: int, cols: int) -> list[tuple[tuple[int, int], tuple[int, int]]]:
    edges: list[tuple[tuple[int, int], tuple[int, int]]] = []
    for i in range(rows):
        for j in range(cols - 1):
            edges.append(((i, j), (i, j + 1)))
    for i in range(rows - 1):
        for j in range(cols):
            edges.append(((i, j), (i + 1, j)))
    return edges


def node_token(value: object) -> str:
    return f"{type(value).__name__}:{value!r}"


def graph_summary(graph: object) -> dict[str, object]:
    nodes = list(graph.nodes())
    edges = list(graph.edges(data=True))
    return {
        "node_count": graph.number_of_nodes(),
        "edge_count": graph.number_of_edges(),
        "nodes_order": [node_token(node) for node in nodes],
        "edges_order": [
            [node_token(u), node_token(v), sorted((str(k), repr(vv)) for k, vv in data.items())]
            for u, v, data in edges
        ],
        "degree_order": [[node_token(node), degree] for node, degree in graph.degree()],
        "graph_attrs": sorted((str(k), repr(v)) for k, v in graph.graph.items()),
        "nodes_seq": getattr(graph, "nodes_seq", None),
        "edges_seq": getattr(graph, "edges_seq", None),
    }


def build_raw_int(module: object, n: int) -> object:
    graph = module.Graph()
    graph.add_edges_from(raw_int_edges(n))
    return graph


def build_raw_tuple(module: object, rows: int, cols: int) -> object:
    graph = module.Graph()
    graph.add_edges_from(raw_tuple_edges(rows, cols))
    return graph


def build_attr(module: object) -> object:
    graph = module.Graph()
    graph.add_edges_from([(0, 1), (1, 2, {"w": 7}), (2, 0)], color="red")
    graph.add_edges_from([(0, 1, {"w": 11})])
    return graph


def case_builders() -> dict[str, Callable[[], object]]:
    return {
        "raw-int": lambda: build_raw_int(fnx, 20_000),
        "raw-tuple": lambda: build_raw_tuple(fnx, 120, 120),
        "ba": lambda: fnx.barabasi_albert_graph(2_000, 4, seed=7),
        "watts": lambda: fnx.watts_strogatz_graph(2_000, 6, 0.25, seed=11),
        "grid": lambda: fnx.grid_2d_graph(60, 60),
    }


def bench(args: argparse.Namespace) -> None:
    builders = case_builders()
    selected = list(builders) if args.case == "all" else [args.case]
    for name in selected:
        times: list[float] = []
        summary: dict[str, object] | None = None
        for _ in range(args.repeat):
            start = time.perf_counter()
            graph = builders[name]()
            elapsed = time.perf_counter() - start
            times.append(elapsed)
            summary = {
                "nodes": graph.number_of_nodes(),
                "edges": graph.number_of_edges(),
                "nodes_seq": getattr(graph, "nodes_seq", None),
                "edges_seq": getattr(graph, "edges_seq", None),
            }
        row = {
            "case": name,
            "repeat": args.repeat,
            "times_s": times,
            "mean_s": statistics.fmean(times),
            "median_s": statistics.median(times),
            "min_s": min(times),
            "max_s": max(times),
            "summary": summary,
        }
        print(json.dumps(row, sort_keys=True))


def golden(args: argparse.Namespace) -> None:
    cases: dict[str, tuple[Callable[[object], object], bool]] = {
        "raw-int-small": (lambda module: build_raw_int(module, 12), True),
        "raw-tuple-small": (lambda module: build_raw_tuple(module, 4, 5), True),
        "attrs": (build_attr, True),
        "ba": (lambda module: module.barabasi_albert_graph(80, 4, seed=7), True),
        "watts": (lambda module: module.watts_strogatz_graph(90, 6, 0.25, seed=11), True),
        "grid": (lambda module: module.grid_2d_graph(6, 7, periodic=True), True),
    }
    output: dict[str, object] = {"cases": {}}
    for name, (builder, compare_nx) in cases.items():
        fnx_graph = builder(fnx)
        fnx_summary = graph_summary(fnx_graph)
        case_out: dict[str, object] = {"fnx": fnx_summary}
        if compare_nx:
            nx_graph = builder(nx)
            nx_summary = graph_summary(nx_graph)
            case_out["nx"] = nx_summary
            case_out["matches_nx_without_counters"] = {
                key: fnx_summary[key] == nx_summary[key]
                for key in (
                    "node_count",
                    "edge_count",
                    "nodes_order",
                    "edges_order",
                    "degree_order",
                    "graph_attrs",
                )
            }
        output["cases"][name] = case_out
    payload = json.dumps(output, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(payload.encode()).hexdigest()
    if args.sha_only:
        print(digest)
    else:
        print(json.dumps({"sha256": digest, "payload": output}, sort_keys=True, indent=2))


def profile(args: argparse.Namespace) -> None:
    builders = case_builders()
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
    bench_parser.add_argument("--case", choices=[*case_builders().keys(), "all"], default="all")
    bench_parser.add_argument("--repeat", type=int, default=5)
    bench_parser.set_defaults(func=bench)
    golden_parser = sub.add_parser("golden")
    golden_parser.add_argument("--sha-only", action="store_true")
    golden_parser.set_defaults(func=golden)
    profile_parser = sub.add_parser("profile")
    profile_parser.add_argument("--case", choices=case_builders().keys(), default="raw-int")
    profile_parser.add_argument("--repeat", type=int, default=20)
    profile_parser.add_argument("--limit", type=int, default=40)
    profile_parser.set_defaults(func=profile)
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
