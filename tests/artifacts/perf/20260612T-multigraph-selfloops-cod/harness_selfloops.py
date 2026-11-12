#!/usr/bin/env python3
"""Benchmark/proof harness for br-r37-c1-5sg97."""

from __future__ import annotations

import argparse
import cProfile
import hashlib
import importlib.util
import json
import os
import pstats
import random
import statistics
import sys
import time
from pathlib import Path
from typing import Any


def _preload_candidate_extension() -> None:
    path = os.environ.get("CANDIDATE_FNX_SO")
    if not path:
        return
    spec = importlib.util.spec_from_file_location("franken_networkx._fnx", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load extension from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["franken_networkx._fnx"] = module
    spec.loader.exec_module(module)


_preload_candidate_extension()

import franken_networkx as fnx  # noqa: E402
import networkx as nx  # noqa: E402


def multigraph_edges(n: int = 150, edge_count: int = 2500) -> list[tuple[int, int]]:
    rng = random.Random(20260612)
    edges: list[tuple[int, int]] = []
    for node in range(0, n, 3):
        for _ in range(1 + (node % 5)):
            edges.append((node, node))
    while len(edges) < edge_count:
        u = rng.randrange(n)
        v = rng.randrange(n)
        if u == v:
            continue
        edges.append((u, v))
    return edges


def build_graph(module: Any, directed: bool = False) -> Any:
    cls = module.MultiDiGraph if directed else module.MultiGraph
    graph = cls()
    graph.add_nodes_from(range(150))
    graph.add_edges_from(multigraph_edges())
    graph.add_edge("x", "x", key="alpha", label="first")
    graph.add_edge("x", "x", key="beta", label="second")
    graph.add_edge("x", 7, key="cross")
    return graph


def payload_for(module: Any) -> dict[str, Any]:
    multi = build_graph(module, directed=False)
    multid = build_graph(module, directed=True)
    return {
        "multigraph_count": module.number_of_selfloops(multi),
        "multidigraph_count": module.number_of_selfloops(multid),
        "multigraph_edges": [(repr(u), repr(v)) for u, v in module.selfloop_edges(multi)],
        "multigraph_edges_keys": [
            (repr(u), repr(v), repr(k))
            for u, v, k in module.selfloop_edges(multi, keys=True)
        ],
        "multidigraph_edges": [(repr(u), repr(v)) for u, v in module.selfloop_edges(multid)],
        "multidigraph_edges_keys": [
            (repr(u), repr(v), repr(k))
            for u, v, k in module.selfloop_edges(multid, keys=True)
        ],
    }


def digest_payload(payload: Any) -> str:
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(blob).hexdigest()


def bench(args: argparse.Namespace) -> None:
    graph = build_graph(fnx, directed=args.directed)
    times: list[float] = []
    result = None
    for _ in range(args.warmups):
        for _ in range(args.calls):
            result = fnx.number_of_selfloops(graph)
    for _ in range(args.samples):
        start = time.perf_counter()
        for _ in range(args.calls):
            result = fnx.number_of_selfloops(graph)
        elapsed = time.perf_counter() - start
        times.append(elapsed / args.calls)
    ordered = sorted(times)
    print(
        json.dumps(
            {
                "calls_per_sample": args.calls,
                "directed": args.directed,
                "engine": "fnx",
                "mean_s_per_call": statistics.mean(times),
                "median_s_per_call": statistics.median(times),
                "min_s_per_call": min(times),
                "p95_s_per_call": ordered[
                    min(len(ordered) - 1, int(len(ordered) * 0.95))
                ],
                "result": result,
                "samples": args.samples,
            },
            sort_keys=True,
        )
    )


def proof(_: argparse.Namespace) -> None:
    fnx_payload = payload_for(fnx)
    nx_payload = payload_for(nx)
    result = {
        "all_match": fnx_payload == nx_payload,
        "fnx_digest": digest_payload(fnx_payload),
        "nx_digest": digest_payload(nx_payload),
        "fnx_payload": fnx_payload,
        "nx_payload": nx_payload,
    }
    print(json.dumps(result, sort_keys=True, indent=2))


def profile(args: argparse.Namespace) -> None:
    output = Path(args.output)
    stats_path = output.with_suffix(".prof")
    graph = build_graph(fnx, directed=args.directed)
    profiler = cProfile.Profile()
    for _ in range(args.warmups):
        for _ in range(args.calls):
            fnx.number_of_selfloops(graph)
    profiler.enable()
    for _ in range(args.calls):
        fnx.number_of_selfloops(graph)
    profiler.disable()
    profiler.dump_stats(stats_path)
    with output.open("w", encoding="utf-8") as fh:
        stats = pstats.Stats(profiler, stream=fh)
        stats.strip_dirs().sort_stats("cumtime").print_stats(args.limit)


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)

    bench_parser = sub.add_parser("bench")
    bench_parser.add_argument("--calls", type=int, default=5000)
    bench_parser.add_argument("--samples", type=int, default=40)
    bench_parser.add_argument("--warmups", type=int, default=3)
    bench_parser.add_argument("--directed", action="store_true")
    bench_parser.set_defaults(func=bench)

    proof_parser = sub.add_parser("proof")
    proof_parser.set_defaults(func=proof)

    profile_parser = sub.add_parser("profile")
    profile_parser.add_argument("--calls", type=int, default=10000)
    profile_parser.add_argument("--warmups", type=int, default=2)
    profile_parser.add_argument("--directed", action="store_true")
    profile_parser.add_argument("--output", required=True)
    profile_parser.add_argument("--limit", type=int, default=30)
    profile_parser.set_defaults(func=profile)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
