#!/usr/bin/env python3
"""Benchmark and parity proof helper for br-r37-c1-dnv8g."""

from __future__ import annotations

import argparse
import cProfile
import hashlib
import io
import json
import pstats
import time
from pathlib import Path
from typing import Any

import franken_networkx as fnx
import networkx as nx


def _edge_payload(graph: Any) -> list[tuple[str, str]]:
    return [(repr(u), repr(v)) for u, v in graph.edges()]


def _node_payload(graph: Any) -> list[str]:
    return [repr(node) for node in graph.nodes()]


def graph_digest(graph: Any) -> dict[str, Any]:
    payload = {
        "nodes": _node_payload(graph),
        "edges": _edge_payload(graph),
        "degree": [(repr(node), degree) for node, degree in graph.degree()],
        "adjacency": [
            (repr(node), [repr(neighbor) for neighbor in graph[node]])
            for node in graph.nodes()
        ],
        "is_directed": graph.is_directed(),
        "is_multigraph": graph.is_multigraph(),
        "node_count": graph.number_of_nodes(),
        "edge_count": graph.number_of_edges(),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return {"sha256": hashlib.sha256(encoded).hexdigest(), "payload": payload}


def make_graph(kind: str, size: int) -> Any:
    if kind == "fnx_native":
        return fnx.grid_2d_graph(size, size)
    if kind == "fnx_fallback":
        return fnx.grid_2d_graph(size, size, periodic=(False, False))
    if kind == "nx":
        return nx.grid_2d_graph(size, size)
    raise ValueError(f"unknown graph kind: {kind}")


def bench(kind: str, size: int, loops: int) -> None:
    start = time.perf_counter()
    total_edges = 0
    for _ in range(loops):
        total_edges += make_graph(kind, size).number_of_edges()
    elapsed = time.perf_counter() - start
    print(
        json.dumps(
            {
                "kind": kind,
                "size": size,
                "loops": loops,
                "total_edges": total_edges,
                "elapsed_seconds": elapsed,
            },
            sort_keys=True,
        )
    )


def golden(size: int, output: Path) -> None:
    results = {
        kind: graph_digest(make_graph(kind, size))
        for kind in ("nx", "fnx_fallback", "fnx_native")
    }
    shas = {kind: value["sha256"] for kind, value in results.items()}
    results["isomorphism"] = {
        "ordering_preserved": shas["nx"] == shas["fnx_native"],
        "fallback_preserved": shas["fnx_fallback"] == shas["fnx_native"],
        "tie_breaking": "node, edge, degree, and adjacency iteration digests match",
        "floating_point": "N/A",
        "rng": "N/A",
    }
    output.write_text(json.dumps(results, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"output": str(output), "sha256": shas}, sort_keys=True))


def profile(kind: str, size: int, loops: int, output: Path) -> None:
    profiler = cProfile.Profile()
    profiler.enable()
    bench(kind, size, loops)
    profiler.disable()
    stream = io.StringIO()
    stats = pstats.Stats(profiler, stream=stream).strip_dirs().sort_stats("cumtime")
    stats.print_stats(30)
    output.write_text(stream.getvalue())


def main() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    bench_parser = subparsers.add_parser("bench")
    bench_parser.add_argument("kind", choices=("fnx_native", "fnx_fallback", "nx"))
    bench_parser.add_argument("--size", type=int, default=60)
    bench_parser.add_argument("--loops", type=int, default=50)

    golden_parser = subparsers.add_parser("golden")
    golden_parser.add_argument("--size", type=int, default=60)
    golden_parser.add_argument("--output", type=Path, required=True)

    profile_parser = subparsers.add_parser("profile")
    profile_parser.add_argument("kind", choices=("fnx_native", "fnx_fallback", "nx"))
    profile_parser.add_argument("--size", type=int, default=60)
    profile_parser.add_argument("--loops", type=int, default=20)
    profile_parser.add_argument("--output", type=Path, required=True)

    args = parser.parse_args()
    if args.command == "bench":
        bench(args.kind, args.size, args.loops)
    elif args.command == "golden":
        golden(args.size, args.output)
    elif args.command == "profile":
        profile(args.kind, args.size, args.loops, args.output)


if __name__ == "__main__":
    main()
