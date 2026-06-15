#!/usr/bin/env python3
"""Profile br-r37-c1-yuxi6 DiGraph edges(data=key) materialization residuals."""

from __future__ import annotations

import argparse
import cProfile
import hashlib
import io
import json
import pstats
import statistics
import time
from pathlib import Path
from typing import Any

import networkx as nx

import franken_networkx as fnx


NODE_COUNT = 5000
EDGE_SPAN = 8


def edge_rows(attr_mode: str) -> list[Any]:
    rows = []
    for u in range(NODE_COUNT):
        for span in range(1, EDGE_SPAN + 1):
            v = (u + span) % NODE_COUNT
            if attr_mode == "full":
                rows.append((u, v, {"w": ((u * 1315423911) ^ (v * 2654435761) ^ span) & 0xFFFF}))
            elif attr_mode == "half" and ((u + span) & 1) == 0:
                rows.append((u, v, {"w": u + v + span}))
            else:
                rows.append((u, v))
    return rows


def build_graph(mod: Any, attr_mode: str) -> Any:
    graph = mod.DiGraph()
    graph.add_nodes_from(range(NODE_COUNT))
    graph.add_edges_from(edge_rows(attr_mode))
    return graph


def normalize(value: Any) -> Any:
    if isinstance(value, tuple):
        return [normalize(item) for item in value]
    if isinstance(value, list):
        return [normalize(item) for item in value]
    if isinstance(value, dict):
        return {str(key): normalize(value[key]) for key in sorted(value)}
    return value


def digest(value: Any) -> str:
    payload = json.dumps(normalize(value), sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def run_case(graph: Any, case: str) -> list[Any]:
    if case == "data_w":
        return list(graph.edges(data="w", default=-1))
    if case == "data_missing":
        return list(graph.edges(data="missing", default=-1))
    if case == "data_true":
        return list(graph.edges(data=True))
    raise ValueError(case)


def summarize(samples: list[float], loops: int) -> dict[str, Any]:
    return {
        "seconds": samples,
        "median": statistics.median(samples),
        "mean": statistics.fmean(samples),
        "per_loop_median_ms": statistics.median(samples) * 1000 / loops,
        "per_loop_mean_ms": statistics.fmean(samples) * 1000 / loops,
    }


def cmd_golden(args: argparse.Namespace) -> int:
    rows = []
    for attr_mode in args.attr_modes:
        nx_graph = build_graph(nx, attr_mode)
        fnx_graph = build_graph(fnx, attr_mode)
        for case in args.cases:
            nx_value = run_case(nx_graph, case)
            fnx_value = run_case(fnx_graph, case)
            rows.append(
                {
                    "attr_mode": attr_mode,
                    "case": case,
                    "length": len(fnx_value),
                    "match": normalize(fnx_value) == normalize(nx_value),
                    "fnx_sha256": digest(fnx_value),
                    "nx_sha256": digest(nx_value),
                    "sample": normalize(fnx_value[:5]),
                }
            )
    payload = {
        "bead": "br-r37-c1-yuxi6",
        "graph": {"nodes": NODE_COUNT, "edges": NODE_COUNT * EDGE_SPAN},
        "cases": rows,
        "semantic_sha256": digest(rows),
        "all_match": all(row["match"] for row in rows),
        "obligations": {
            "ordering": "Exact insertion-order edge output compared against NetworkX.",
            "tie_breaking": "N/A beyond insertion order.",
            "floating_point": "N/A; integer ids and integer/default data only.",
            "rng": "N/A; deterministic graph construction.",
        },
    }
    args.output.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n")
    return 0 if payload["all_match"] else 1


def cmd_bench(args: argparse.Namespace) -> int:
    rows = []
    for which in args.which:
        mod = fnx if which == "fnx" else nx
        for attr_mode in args.attr_modes:
            graph = build_graph(mod, attr_mode)
            for case in args.cases:
                for _ in range(args.warmup):
                    run_case(graph, case)
                samples = []
                checksum = 0
                for _ in range(args.repeats):
                    start = time.perf_counter()
                    for _ in range(args.loops):
                        checksum += len(run_case(graph, case))
                    samples.append(time.perf_counter() - start)
                row = summarize(samples, args.loops)
                row.update(
                    {
                        "which": which,
                        "attr_mode": attr_mode,
                        "case": case,
                        "checksum": checksum,
                    }
                )
                rows.append(row)
    args.output.write_text(json.dumps({"rows": rows}, sort_keys=True, indent=2) + "\n")
    return 0


def cmd_loop(args: argparse.Namespace) -> int:
    mod = fnx if args.which == "fnx" else nx
    graph = build_graph(mod, args.attr_mode)
    for _ in range(args.warmup):
        run_case(graph, args.case)
    checksum = 0
    for _ in range(args.loops):
        checksum += len(run_case(graph, args.case))
    print(checksum)
    return 0


def cmd_profile(args: argparse.Namespace) -> int:
    mod = fnx if args.which == "fnx" else nx
    graph = build_graph(mod, args.attr_mode)
    for _ in range(args.warmup):
        run_case(graph, args.case)
    profiler = cProfile.Profile()
    profiler.enable()
    checksum = 0
    for _ in range(args.loops):
        checksum += len(run_case(graph, args.case))
    profiler.disable()
    output = io.StringIO()
    print(
        f"bead=br-r37-c1-yuxi6 which={args.which} attr_mode={args.attr_mode} "
        f"case={args.case} loops={args.loops} checksum={checksum}",
        file=output,
    )
    stats = pstats.Stats(profiler, stream=output)
    stats.sort_stats("cumtime").print_stats(args.limit)
    print("\n--- tottime ---", file=output)
    stats.sort_stats("tottime").print_stats(args.limit)
    args.output.write_text(output.getvalue())
    return 0


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_golden = sub.add_parser("golden")
    p_golden.add_argument("--output", type=Path, required=True)
    p_golden.add_argument("--attr-modes", nargs="+", default=["full", "half", "none"])
    p_golden.add_argument("--cases", nargs="+", default=["data_w", "data_missing", "data_true"])

    p_bench = sub.add_parser("bench")
    p_bench.add_argument("--output", type=Path, required=True)
    p_bench.add_argument("--which", nargs="+", default=["fnx", "nx"])
    p_bench.add_argument("--attr-modes", nargs="+", default=["full", "half", "none"])
    p_bench.add_argument("--cases", nargs="+", default=["data_w", "data_missing", "data_true"])
    p_bench.add_argument("--loops", type=int, default=60)
    p_bench.add_argument("--repeats", type=int, default=7)
    p_bench.add_argument("--warmup", type=int, default=3)

    p_loop = sub.add_parser("loop")
    p_loop.add_argument("--which", choices=["fnx", "nx"], required=True)
    p_loop.add_argument("--attr-mode", choices=["full", "half", "none"], required=True)
    p_loop.add_argument("--case", choices=["data_w", "data_missing", "data_true"], required=True)
    p_loop.add_argument("--loops", type=int, default=60)
    p_loop.add_argument("--warmup", type=int, default=3)

    p_profile = sub.add_parser("profile")
    p_profile.add_argument("--which", choices=["fnx", "nx"], required=True)
    p_profile.add_argument("--attr-mode", choices=["full", "half", "none"], required=True)
    p_profile.add_argument("--case", choices=["data_w", "data_missing", "data_true"], required=True)
    p_profile.add_argument("--loops", type=int, default=60)
    p_profile.add_argument("--warmup", type=int, default=3)
    p_profile.add_argument("--limit", type=int, default=35)
    p_profile.add_argument("--output", type=Path, required=True)

    args = parser.parse_args()
    raise SystemExit(globals()[f"cmd_{args.cmd}"](args))


if __name__ == "__main__":
    main()
