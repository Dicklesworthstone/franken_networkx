#!/usr/bin/env python3
"""Proof and benchmark harness for Graph integer-side node removal."""

from __future__ import annotations

import argparse
import cProfile
import hashlib
import io
import json
import pstats
import statistics
import time
from collections.abc import Iterable
from typing import Any

import franken_networkx as fnx
import networkx as nx


def edge_stream(n: int, m: int) -> list[tuple[int, int, dict[str, int]]]:
    edges: list[tuple[int, int, dict[str, int]]] = []
    seen: set[tuple[int, int]] = set()
    for u in range(n):
        v = (u + 1) % n
        left, right = (u, v) if u <= v else (v, u)
        seen.add((left, right))
        edges.append((left, right, {"w": (left * 17 + right) % 101}))
    for stride in range(2, n):
        for u in range(n):
            v = (u + stride) % n
            left, right = (u, v) if u <= v else (v, u)
            key = (left, right)
            if key in seen:
                continue
            seen.add(key)
            edges.append((left, right, {"w": (left * 17 + right) % 101}))
            if len(edges) >= m:
                return edges
    raise ValueError(f"requested {m} edges but only built {len(edges)}")


def build_graph(module: Any, n: int, m: int) -> Any:
    graph = module.Graph()
    graph.add_nodes_from(range(n))
    graph.add_edges_from(edge_stream(n, m))
    return graph


def victims(n: int, mode: str) -> Iterable[int]:
    if mode == "half":
        return range(0, n, 2)
    if mode == "thirds":
        return [node for node in range(n) if node % 3 == 1]
    if mode == "single_hot":
        return [0]
    raise ValueError(f"unknown mode: {mode}")


def stable_record(graph: Any) -> dict[str, Any]:
    return {
        "nodes": list(graph.nodes()),
        "edges": [(u, v, dict(attrs)) for u, v, attrs in graph.edges(data=True)],
        "degree": list(graph.degree()),
        "node_count": graph.number_of_nodes(),
        "edge_count": graph.number_of_edges(),
    }


def digest(payload: Any) -> str:
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=repr).encode()
    return hashlib.sha256(blob).hexdigest()


def remove_once(module: Any, n: int, m: int, mode: str) -> tuple[float, Any]:
    graph = build_graph(module, n, m)
    start = time.perf_counter()
    if mode == "single_hot":
        graph.remove_node(0)
    else:
        graph.remove_nodes_from(victims(n, mode))
    elapsed = time.perf_counter() - start
    return elapsed, graph


def run_proof(args: argparse.Namespace) -> None:
    records = []
    timings = {}
    for mode in ("half", "thirds", "single_hot"):
        fnx_elapsed, fnx_graph = remove_once(fnx, args.nodes, args.edges, mode)
        nx_elapsed, nx_graph = remove_once(nx, args.nodes, args.edges, mode)
        fnx_record = stable_record(fnx_graph)
        nx_record = stable_record(nx_graph)
        records.append(
            {
                "mode": mode,
                "fnx": fnx_record,
                "matches": fnx_record == nx_record,
                "nx": nx_record,
            }
        )
        timings[mode] = {"fnx": fnx_elapsed, "nx": nx_elapsed}
    print(
        json.dumps(
            {
                "cases": len(records),
                "golden_sha256": digest(records),
                "records": records,
                "timed_s": timings,
            },
            sort_keys=True,
        )
    )
    if not all(record["matches"] for record in records):
        raise SystemExit(1)


def run_bench(args: argparse.Namespace) -> None:
    module = fnx if args.impl == "fnx" else nx
    timings = []
    last_record = None
    for _ in range(args.samples):
        elapsed, graph = remove_once(module, args.nodes, args.edges, args.mode)
        timings.append(elapsed)
        last_record = stable_record(graph)
    print(
        json.dumps(
            {
                "digest": digest(last_record),
                "edges": args.edges,
                "impl": args.impl,
                "max_s": max(timings),
                "mean_s": statistics.fmean(timings),
                "median_s": statistics.median(timings),
                "min_s": min(timings),
                "mode": args.mode,
                "nodes": args.nodes,
                "samples": args.samples,
            },
            sort_keys=True,
        )
    )


def run_loop(args: argparse.Namespace) -> None:
    total_edges = 0
    for _ in range(args.loops):
        _, graph = remove_once(fnx, args.nodes, args.edges, args.mode)
        total_edges += graph.number_of_edges()
    print(
        json.dumps(
            {
                "edges": args.edges,
                "loops": args.loops,
                "mode": args.mode,
                "nodes": args.nodes,
                "total_edges": total_edges,
            },
            sort_keys=True,
        )
    )


def run_profile(args: argparse.Namespace) -> None:
    profiler = cProfile.Profile()
    profiler.enable()
    for _ in range(args.loops):
        remove_once(fnx, args.nodes, args.edges, args.mode)
    profiler.disable()
    stream = io.StringIO()
    pstats.Stats(profiler, stream=stream).sort_stats("cumulative").print_stats(args.limit)
    print(stream.getvalue())


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    proof = sub.add_parser("proof")
    proof.add_argument("--nodes", type=int, default=320)
    proof.add_argument("--edges", type=int, default=2400)
    proof.set_defaults(func=run_proof)

    bench = sub.add_parser("bench")
    bench.add_argument("--impl", choices=("fnx", "nx"), required=True)
    bench.add_argument("--mode", choices=("half", "thirds", "single_hot"), default="half")
    bench.add_argument("--nodes", type=int, default=3000)
    bench.add_argument("--edges", type=int, default=36000)
    bench.add_argument("--samples", type=int, default=12)
    bench.set_defaults(func=run_bench)

    loop = sub.add_parser("loop")
    loop.add_argument("--mode", choices=("half", "thirds", "single_hot"), default="half")
    loop.add_argument("--nodes", type=int, default=3000)
    loop.add_argument("--edges", type=int, default=36000)
    loop.add_argument("--loops", type=int, default=8)
    loop.set_defaults(func=run_loop)

    profile = sub.add_parser("profile")
    profile.add_argument("--mode", choices=("half", "thirds", "single_hot"), default="half")
    profile.add_argument("--nodes", type=int, default=3000)
    profile.add_argument("--edges", type=int, default=36000)
    profile.add_argument("--loops", type=int, default=4)
    profile.add_argument("--limit", type=int, default=40)
    profile.set_defaults(func=run_profile)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
