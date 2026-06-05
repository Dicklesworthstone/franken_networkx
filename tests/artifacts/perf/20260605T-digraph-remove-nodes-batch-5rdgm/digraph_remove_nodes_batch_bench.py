#!/usr/bin/env python3
"""Deterministic DiGraph.remove_nodes_from benchmark and parity harness."""

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
from pathlib import Path
from typing import Any

import franken_networkx as fnx
import networkx as nx


def edge_stream(n: int, m: int) -> list[tuple[int, int, dict[str, int]]]:
    edges: list[tuple[int, int, dict[str, int]]] = []
    seen: set[tuple[int, int]] = set()
    for node in range(n):
        edge = (node, (node + 1) % n)
        seen.add(edge)
        edges.append((*edge, {"w": node % 17, "tag": node}))
    stride_order = list(range(2, n))
    stride_order.sort(key=lambda value: ((value * 41) % n, value))
    for stride in stride_order:
        for source in range(n):
            target = (source + stride) % n
            edge = (source, target)
            if edge in seen:
                continue
            seen.add(edge)
            edges.append((*edge, {"w": (source + stride) % 17, "tag": len(edges)}))
            if len(edges) >= m:
                return edges
    if len(edges) < m:
        raise ValueError(f"requested {m} edges but only built {len(edges)}")
    return edges


def build_graph(module: Any, n: int, m: int) -> Any:
    graph = module.DiGraph()
    graph.add_nodes_from((node, {"label": f"n{node}"}) for node in range(n))
    graph.add_edges_from(edge_stream(n, m))
    return graph


def removal_nodes(n: int, style: str) -> Iterable[int]:
    values = [node for node in range(n) if node % 2 == 0 or node % 11 == 0]
    values.extend([n + 100, 0, 0])
    if style == "range":
        return (node for node in values)
    if style == "list":
        return list(values)
    if style == "tuple":
        return tuple(values)
    raise ValueError(f"unknown removal node style: {style}")


def run_once(module: Any, n: int, m: int, style: str) -> tuple[float, Any]:
    graph = build_graph(module, n, m)
    victims = removal_nodes(n, style)
    started = time.perf_counter()
    graph.remove_nodes_from(victims)
    elapsed = time.perf_counter() - started
    return elapsed, graph


def stable_graph_record(graph: Any) -> dict[str, Any]:
    return {
        "nodes": [(node, dict(attrs)) for node, attrs in graph.nodes(data=True)],
        "edges": [(u, v, dict(attrs)) for u, v, attrs in graph.edges(data=True)],
        "out_degree": list(graph.out_degree()),
        "in_degree": list(graph.in_degree()),
        "node_count": graph.number_of_nodes(),
        "edge_count": graph.number_of_edges(),
    }


def digest_records(records: list[dict[str, Any]]) -> str:
    payload = json.dumps(records, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def bench(args: argparse.Namespace) -> None:
    module = fnx if args.impl == "fnx" else nx
    times: list[float] = []
    digest = ""
    for _ in range(args.loops):
        elapsed, graph = run_once(module, args.nodes, args.edges, args.style)
        times.append(elapsed)
        digest = digest_records([stable_graph_record(graph)])
    result = {
        "impl": args.impl,
        "style": args.style,
        "nodes": args.nodes,
        "edges": args.edges,
        "loops": args.loops,
        "mean": statistics.fmean(times),
        "median": statistics.median(times),
        "min": min(times),
        "max": max(times),
        "digest": digest,
    }
    print(json.dumps(result, sort_keys=True))


def golden(args: argparse.Namespace) -> None:
    records: list[dict[str, Any]] = []
    for style in ("range", "list", "tuple"):
        _, graph_f = run_once(fnx, args.nodes, args.edges, style)
        _, graph_n = run_once(nx, args.nodes, args.edges, style)
        fnx_record = stable_graph_record(graph_f)
        nx_record = stable_graph_record(graph_n)
        records.append(
            {
                "style": style,
                "fnx": fnx_record,
                "nx": nx_record,
                "matches": fnx_record == nx_record,
            }
        )
    digest = digest_records(records)
    for record in records:
        print(json.dumps(record, sort_keys=True))
    print(json.dumps({"golden_sha256": digest}, sort_keys=True))
    if not all(record["matches"] for record in records):
        raise SystemExit(1)


def profile(args: argparse.Namespace) -> None:
    profiler = cProfile.Profile()
    profiler.enable()
    _, graph = run_once(fnx, args.nodes, args.edges, args.style)
    profiler.disable()
    output = io.StringIO()
    stats = pstats.Stats(profiler, stream=output).sort_stats("cumulative")
    stats.print_stats(args.limit)
    Path(args.output).write_text(output.getvalue(), encoding="utf-8")
    print(
        json.dumps(
            {
                "impl": "fnx",
                "style": args.style,
                "nodes": args.nodes,
                "edges": args.edges,
                "digest": digest_records([stable_graph_record(graph)]),
                "profile": args.output,
            },
            sort_keys=True,
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    bench_parser = subparsers.add_parser("bench")
    bench_parser.add_argument("--impl", choices=("fnx", "nx"), required=True)
    bench_parser.add_argument("--style", choices=("range", "list", "tuple"), default="range")
    bench_parser.add_argument("--nodes", type=int, default=2000)
    bench_parser.add_argument("--edges", type=int, default=16000)
    bench_parser.add_argument("--loops", type=int, default=20)
    bench_parser.set_defaults(func=bench)

    golden_parser = subparsers.add_parser("golden")
    golden_parser.add_argument("--nodes", type=int, default=300)
    golden_parser.add_argument("--edges", type=int, default=1600)
    golden_parser.set_defaults(func=golden)

    profile_parser = subparsers.add_parser("profile")
    profile_parser.add_argument("--style", choices=("range", "list", "tuple"), default="range")
    profile_parser.add_argument("--nodes", type=int, default=2000)
    profile_parser.add_argument("--edges", type=int, default=16000)
    profile_parser.add_argument("--output", required=True)
    profile_parser.add_argument("--limit", type=int, default=40)
    profile_parser.set_defaults(func=profile)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
