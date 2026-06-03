#!/usr/bin/env python3
"""Benchmark raw bfs_tree construction without edge-view normalization in the timer."""

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

import franken_networkx as fnx
import networkx as nx


def build_graph(engine: str, n: int, m: int, seed: int):
    module = fnx if engine == "fnx" else nx
    return module.barabasi_albert_graph(n, m, seed=seed)


def digest_tree(tree) -> str:
    payload = {
        "nodes": list(tree.nodes()),
        "edges": list(tree.edges()),
    }
    return hashlib.sha256(json.dumps(payload, default=repr).encode()).hexdigest()


def run_samples(engine: str, n: int, m: int, seed: int, repeat: int):
    graph = build_graph(engine, n, m, seed)
    module = fnx if engine == "fnx" else nx
    samples = []
    tree = None
    for _ in range(repeat):
        started = time.perf_counter()
        tree = module.bfs_tree(graph, 0)
        samples.append(time.perf_counter() - started)
    return {
        "engine": engine,
        "n": n,
        "m": m,
        "seed": seed,
        "repeat": repeat,
        "mean_seconds": statistics.fmean(samples),
        "p50_seconds": statistics.median(samples),
        "min_seconds": min(samples),
        "max_seconds": max(samples),
        "sha256": digest_tree(tree),
    }


def command_bench(args):
    rows = [
        run_samples(engine, args.n, args.m, args.seed, args.repeat)
        for engine in args.engines
    ]
    print(json.dumps({"rows": rows}, sort_keys=True))


def command_profile(args):
    profiler = cProfile.Profile()
    profiler.enable()
    row = run_samples("fnx", args.n, args.m, args.seed, args.repeat)
    profiler.disable()

    stream = io.StringIO()
    pstats.Stats(profiler, stream=stream).sort_stats("cumtime").print_stats(args.limit)
    Path(args.output).write_text(stream.getvalue())
    print(json.dumps(row, sort_keys=True))


def main():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    bench = subparsers.add_parser("bench")
    bench.add_argument("--n", type=int, default=3000)
    bench.add_argument("--m", type=int, default=4)
    bench.add_argument("--seed", type=int, default=42)
    bench.add_argument("--repeat", type=int, default=50)
    bench.add_argument("--engines", nargs="+", choices=("fnx", "nx"), default=["fnx", "nx"])
    bench.set_defaults(func=command_bench)

    profile = subparsers.add_parser("profile")
    profile.add_argument("--n", type=int, default=3000)
    profile.add_argument("--m", type=int, default=4)
    profile.add_argument("--seed", type=int, default=42)
    profile.add_argument("--repeat", type=int, default=50)
    profile.add_argument("--output", required=True)
    profile.add_argument("--limit", type=int, default=60)
    profile.set_defaults(func=command_profile)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
