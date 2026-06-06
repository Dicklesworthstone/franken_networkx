#!/usr/bin/env python3
"""Benchmark and parity harness for br-r37-c1-dnv8g."""

from __future__ import annotations

import argparse
import cProfile
import hashlib
import json
import pstats
import time
from io import StringIO

import franken_networkx as fnx
import networkx as nx


def _impl(name: str):
    if name == "fnx":
        return fnx
    if name == "nx":
        return nx
    raise ValueError(name)


def _graph_digest(module, m: int, n: int, *, periodic=False, create_using=None):
    try:
        graph = module.grid_2d_graph(m, n, periodic=periodic, create_using=create_using)
    except Exception as exc:  # noqa: BLE001 - exact exception text is part of parity.
        return {
            "ok": False,
            "exception_type": type(exc).__name__,
            "exception_text": str(exc),
        }

    nodes = list(graph.nodes())
    edges = list(graph.edges())
    adjacency = {repr(node): [repr(neighbor) for neighbor in graph.adj[node]] for node in nodes}
    return {
        "ok": True,
        "type": type(graph).__name__,
        "is_directed": graph.is_directed(),
        "node_count": graph.number_of_nodes(),
        "edge_count": graph.number_of_edges(),
        "graph_attrs": sorted((repr(key), repr(value)) for key, value in graph.graph.items()),
        "nodes": [repr(node) for node in nodes],
        "edges": [repr(edge) for edge in edges],
        "adjacency": adjacency,
    }


def golden() -> dict:
    cases = [
        {"name": "empty_rows", "m": 0, "n": 5},
        {"name": "empty_cols", "m": 5, "n": 0},
        {"name": "single", "m": 1, "n": 1},
        {"name": "small_rect", "m": 2, "n": 3},
        {"name": "small_square", "m": 3, "n": 3},
        {"name": "benchmark_shape", "m": 60, "n": 60},
        {"name": "periodic_fallback", "m": 4, "n": 5, "periodic": True},
        {"name": "digraph_fallback", "m": 4, "n": 5, "create_using": nx.DiGraph()},
    ]
    payload = []
    for case in cases:
        descriptor = {}
        for key, value in case.items():
            if key == "create_using":
                descriptor[key] = type(value).__name__
            else:
                descriptor[key] = value
        kwargs = {
            "periodic": case.get("periodic", False),
            "create_using": case.get("create_using"),
        }
        fnx_digest = _graph_digest(fnx, case["m"], case["n"], **kwargs)
        nx_digest = _graph_digest(nx, case["m"], case["n"], **kwargs)
        payload.append(
            {
                "case": descriptor,
                "fnx": fnx_digest,
                "nx": nx_digest,
                "equal": fnx_digest == nx_digest,
            }
        )
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return {
        "sha256": hashlib.sha256(encoded).hexdigest(),
        "all_equal": all(item["equal"] for item in payload),
        "payload": payload,
    }


def bench(impl_name: str, m: int, n: int, loops: int) -> dict:
    module = _impl(impl_name)
    started = time.perf_counter()
    total_nodes = 0
    total_edges = 0
    for _ in range(loops):
        graph = module.grid_2d_graph(m, n)
        total_nodes += graph.number_of_nodes()
        total_edges += graph.number_of_edges()
    elapsed = time.perf_counter() - started
    return {
        "impl": impl_name,
        "m": m,
        "n": n,
        "loops": loops,
        "elapsed_s": elapsed,
        "per_loop_s": elapsed / loops,
        "total_nodes": total_nodes,
        "total_edges": total_edges,
    }


def profile(impl_name: str, m: int, n: int, loops: int, limit: int) -> str:
    profiler = cProfile.Profile()
    profiler.enable()
    bench(impl_name, m, n, loops)
    profiler.disable()
    output = StringIO()
    stats = pstats.Stats(profiler, stream=output).sort_stats("cumulative")
    stats.print_stats(limit)
    return output.getvalue()


def main() -> None:
    parser = argparse.ArgumentParser()
    subcommands = parser.add_subparsers(dest="command", required=True)

    golden_parser = subcommands.add_parser("golden")
    golden_parser.set_defaults(func=lambda _args: golden())

    bench_parser = subcommands.add_parser("bench")
    bench_parser.add_argument("--impl", choices=["fnx", "nx"], required=True)
    bench_parser.add_argument("--m", type=int, default=60)
    bench_parser.add_argument("--n", type=int, default=60)
    bench_parser.add_argument("--loops", type=int, default=20)
    bench_parser.set_defaults(func=lambda args: bench(args.impl, args.m, args.n, args.loops))

    profile_parser = subcommands.add_parser("profile")
    profile_parser.add_argument("--impl", choices=["fnx", "nx"], required=True)
    profile_parser.add_argument("--m", type=int, default=60)
    profile_parser.add_argument("--n", type=int, default=60)
    profile_parser.add_argument("--loops", type=int, default=5)
    profile_parser.add_argument("--limit", type=int, default=40)
    profile_parser.set_defaults(
        func=lambda args: profile(args.impl, args.m, args.n, args.loops, args.limit)
    )

    args = parser.parse_args()
    result = args.func(args)
    if isinstance(result, str):
        print(result, end="")
    else:
        print(json.dumps(result, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
