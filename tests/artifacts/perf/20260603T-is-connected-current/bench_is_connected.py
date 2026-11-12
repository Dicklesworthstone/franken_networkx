#!/usr/bin/env python3
"""Focused is_connected residual benchmark for br-r37-c1-04z53.19."""

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
from pathlib import Path
from typing import Any

import networkx as nx

import franken_networkx as fnx


def _build_graphs(n: int, m: int, seed: int) -> tuple[Any, Any]:
    nx_graph = nx.barabasi_albert_graph(n, m, seed=seed)
    fnx_graph = fnx.Graph()
    fnx_graph.add_nodes_from(nx_graph.nodes())
    fnx_graph.add_edges_from(nx_graph.edges())
    return fnx_graph, nx_graph


def _digest(result: bool, *, n: int, m: int, seed: int, edges: int) -> str:
    payload = json.dumps(
        {
            "case": "is_connected_ba",
            "n": n,
            "m": m,
            "seed": seed,
            "edges": edges,
            "result": bool(result),
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return hashlib.sha256(payload).hexdigest()


def _time_call(func: Callable[[], bool], repeats: int) -> tuple[list[float], bool]:
    samples: list[float] = []
    last = False
    for _ in range(repeats):
        start = time.perf_counter()
        last = func()
        samples.append(time.perf_counter() - start)
    return samples, last


def _emit(record: dict[str, Any]) -> None:
    print(json.dumps(record, sort_keys=True, separators=(",", ":")), flush=True)


def _select(args: argparse.Namespace) -> tuple[Any, Any]:
    fnx_graph, nx_graph = _build_graphs(args.n, args.m, args.seed)
    return (fnx, fnx_graph) if args.impl == "fnx" else (nx, nx_graph)


def run_bench(args: argparse.Namespace) -> int:
    module, graph = _select(args)
    samples, result = _time_call(lambda: module.is_connected(graph), args.repeats)
    _emit(
        {
            "case": "is_connected_ba",
            "impl": args.impl,
            "n": args.n,
            "m": args.m,
            "seed": args.seed,
            "edges": graph.number_of_edges(),
            "repeats": args.repeats,
            "mean_sec": statistics.fmean(samples),
            "median_sec": statistics.median(samples),
            "min_sec": min(samples),
            "max_sec": max(samples),
            "samples_sec": samples,
            "result": bool(result),
            "digest": _digest(
                bool(result),
                n=args.n,
                m=args.m,
                seed=args.seed,
                edges=graph.number_of_edges(),
            ),
        }
    )
    return 0


def run_profile(args: argparse.Namespace) -> int:
    module, graph = _select(args)
    profiler = cProfile.Profile()
    profiler.enable()
    result = False
    for _ in range(args.repeats):
        result = bool(module.is_connected(graph))
    profiler.disable()
    stream = io.StringIO()
    pstats.Stats(profiler, stream=stream).strip_dirs().sort_stats("cumulative").print_stats(
        args.limit
    )
    Path(args.output).write_text(stream.getvalue(), encoding="utf-8")
    _emit(
        {
            "case": "is_connected_ba",
            "impl": args.impl,
            "n": args.n,
            "m": args.m,
            "seed": args.seed,
            "edges": graph.number_of_edges(),
            "repeats": args.repeats,
            "result": bool(result),
            "digest": _digest(
                bool(result),
                n=args.n,
                m=args.m,
                seed=args.seed,
                edges=graph.number_of_edges(),
            ),
            "profile": args.output,
        }
    )
    return 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="cmd", required=True)
    for command in ("bench", "profile"):
        sub = subparsers.add_parser(command)
        sub.add_argument("--impl", choices=["fnx", "nx"], required=True)
        sub.add_argument("--n", type=int, default=5000)
        sub.add_argument("--m", type=int, default=4)
        sub.add_argument("--seed", type=int, default=42)
        sub.add_argument("--repeats", type=int, default=12)
        if command == "profile":
            sub.add_argument("--output", required=True)
            sub.add_argument("--limit", type=int, default=60)
            sub.set_defaults(func=run_profile)
        else:
            sub.set_defaults(func=run_bench)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
