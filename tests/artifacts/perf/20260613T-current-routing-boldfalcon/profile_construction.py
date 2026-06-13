#!/usr/bin/env python3
"""Current-head construction residual harness."""

from __future__ import annotations

import argparse
import cProfile
import hashlib
import json
import pstats
import statistics
import time
from io import StringIO
from typing import Any

import franken_networkx as fnx
import networkx as nx


def _digest_graph(graph: Any) -> str:
    payload = {
        "nodes": list(graph.nodes()),
        "edges": list(graph.edges(keys=True)) if graph.is_multigraph() else list(graph.edges()),
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def _plain_edges(size: int) -> list[tuple[int, int]]:
    return [(i, i + 1) for i in range(size)]


def _multi_edges_int(size: int) -> list[tuple[int, int, int]]:
    return [(i, i + 1, i) for i in range(size)]


def _multi_edges_str(size: int) -> list[tuple[int, int, str]]:
    return [(i, i + 1, f"k{i}") for i in range(size)]


def run_case(impl: str, case: str, size: int) -> Any:
    mod = fnx if impl == "fnx" else nx
    if case == "add_nodes_int":
        graph = mod.Graph()
        graph.add_nodes_from(range(size))
        return graph
    if case == "plain_edges_int":
        graph = mod.Graph()
        graph.add_edges_from(_plain_edges(size))
        return graph
    if case == "multigraph_int_keys":
        graph = mod.MultiGraph()
        graph.add_edges_from(_multi_edges_int(size))
        return graph
    if case == "multigraph_str_keys":
        graph = mod.MultiGraph()
        graph.add_edges_from(_multi_edges_str(size))
        return graph
    raise ValueError(case)


def command_sweep(args: argparse.Namespace) -> int:
    rows = []
    for case in args.case:
        size = args.size
        case_rows = []
        for impl in ("fnx", "nx"):
            samples = []
            digest = None
            nodes = None
            edges = None
            for _ in range(args.repeats):
                start = time.perf_counter()
                graph = run_case(impl, case, size)
                samples.append(time.perf_counter() - start)
                digest = _digest_graph(graph)
                nodes = graph.number_of_nodes()
                edges = graph.number_of_edges()
            case_rows.append(
                {
                    "case": case,
                    "digest": digest,
                    "edges": edges,
                    "impl": impl,
                    "max_sec": max(samples),
                    "mean_sec": statistics.fmean(samples),
                    "median_sec": statistics.median(samples),
                    "min_sec": min(samples),
                    "nodes": nodes,
                    "repeats": args.repeats,
                    "samples_sec": samples,
                    "size": size,
                }
            )
        fnx_row = next(row for row in case_rows if row["impl"] == "fnx")
        nx_row = next(row for row in case_rows if row["impl"] == "nx")
        rows.append(
            {
                "case": case,
                "digests_match": fnx_row["digest"] == nx_row["digest"],
                "fnx_over_nx": fnx_row["median_sec"] / nx_row["median_sec"],
                "records": case_rows,
            }
        )
    print(json.dumps({"impl": "current-head construction routing", "rows": rows}, sort_keys=True))
    return 0


def command_profile(args: argparse.Namespace) -> int:
    profiler = cProfile.Profile()
    profiler.enable()
    for _ in range(args.repeats):
        graph = run_case("fnx", args.case, args.size)
    profiler.disable()
    out = StringIO()
    pstats.Stats(profiler, stream=out).sort_stats("cumtime").print_stats(args.limit)
    print(
        "case="
        + args.case
        + " sha256="
        + _digest_graph(graph)
        + "\n"
        + out.getvalue()
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    choices = (
        "add_nodes_int",
        "plain_edges_int",
        "multigraph_int_keys",
        "multigraph_str_keys",
    )

    sweep = sub.add_parser("sweep")
    sweep.add_argument("--case", choices=choices, action="append", default=list(choices))
    sweep.add_argument("--size", type=int, default=50000)
    sweep.add_argument("--repeats", type=int, default=7)
    sweep.set_defaults(func=command_sweep)

    profile = sub.add_parser("profile")
    profile.add_argument("case", choices=choices)
    profile.add_argument("--size", type=int, default=50000)
    profile.add_argument("--repeats", type=int, default=5)
    profile.add_argument("--limit", type=int, default=40)
    profile.set_defaults(func=command_profile)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
