#!/usr/bin/env python3
"""Residual clustering-family profiler for the no-gaps campaign."""

from __future__ import annotations

import argparse
import cProfile
import gc
import hashlib
import io
import json
import pstats
import time
from typing import Any, Callable

import franken_networkx as fnx
import networkx as nx


OPS = ("triangles", "clustering", "average_clustering", "transitivity")


def build_pair(n: int, m: int, seed: int) -> tuple[Any, Any]:
    base = nx.barabasi_albert_graph(n, m, seed=seed)
    rust_graph = fnx.Graph()
    rust_graph.add_nodes_from(base.nodes())
    rust_graph.add_edges_from(base.edges())
    return rust_graph, base


def op_func(module: Any, op: str) -> Callable[[Any], Any]:
    return getattr(module, op)


def normalize(value: Any) -> Any:
    if isinstance(value, dict):
        return {repr(k): normalize(v) for k, v in sorted(value.items(), key=lambda item: repr(item[0]))}
    if isinstance(value, float):
        return repr(value)
    if isinstance(value, (list, tuple)):
        return [normalize(v) for v in value]
    return value


def call(impl: str, op: str, graph_f: Any, graph_n: Any) -> Any:
    module = fnx if impl == "fnx" else nx
    graph = graph_f if impl == "fnx" else graph_n
    return op_func(module, op)(graph)


def sample(impl: str, op: str, repeat: int, n: int, m: int, seed: int) -> dict[str, Any]:
    graph_f, graph_n = build_pair(n, m, seed)
    outputs: list[Any] = []
    durations: list[float] = []

    gc.collect()
    gc.disable()
    try:
        for _ in range(repeat):
            start = time.perf_counter()
            out = call(impl, op, graph_f, graph_n)
            durations.append(time.perf_counter() - start)
            outputs.append(normalize(out))
    finally:
        gc.enable()

    payload = json.dumps(outputs, sort_keys=True, separators=(",", ":")).encode()
    ordered = sorted(durations)
    return {
        "impl": impl,
        "op": op,
        "repeat": repeat,
        "n": n,
        "m": m,
        "graph_seed": seed,
        "mean_seconds": sum(durations) / len(durations),
        "min_seconds": ordered[0],
        "p50_seconds": ordered[len(ordered) // 2],
        "max_seconds": ordered[-1],
        "sha256": hashlib.sha256(payload).hexdigest(),
    }


def sweep(repeat: int, n: int, m: int, seed: int) -> list[dict[str, Any]]:
    rows = []
    for op in OPS:
        fnx_row = sample("fnx", op, repeat, n, m, seed)
        nx_row = sample("nx", op, repeat, n, m, seed)
        rows.extend([fnx_row, nx_row])
    return rows


def profile(op: str, repeat: int, n: int, m: int, seed: int) -> str:
    profiler = cProfile.Profile()
    profiler.enable()
    sample("fnx", op, repeat, n, m, seed)
    profiler.disable()
    stream = io.StringIO()
    pstats.Stats(profiler, stream=stream).sort_stats("cumulative").print_stats(40)
    return stream.getvalue()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["sample", "sweep", "profile"])
    parser.add_argument("--impl", choices=["fnx", "nx"], default="fnx")
    parser.add_argument("--op", choices=OPS, default="triangles")
    parser.add_argument("--repeat", type=int, default=5)
    parser.add_argument("--n", type=int, default=2000)
    parser.add_argument("--m", type=int, default=4)
    parser.add_argument("--graph-seed", type=int, default=42)
    args = parser.parse_args()

    if args.mode == "sweep":
        for row in sweep(args.repeat, args.n, args.m, args.graph_seed):
            print(json.dumps(row, sort_keys=True))
    elif args.mode == "profile":
        print(profile(args.op, args.repeat, args.n, args.m, args.graph_seed))
    else:
        print(
            json.dumps(
                sample(args.impl, args.op, args.repeat, args.n, args.m, args.graph_seed),
                sort_keys=True,
            )
        )


if __name__ == "__main__":
    main()
