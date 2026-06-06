#!/usr/bin/env python3
"""Benchmark and parity harness for br-r37-c1-zt6lj."""

from __future__ import annotations

import argparse
import cProfile
import hashlib
import io
import json
import pstats
import random
import time
from io import StringIO

import franken_networkx as fnx
import networkx as nx


def edge_list(n: int, edges: int, seed: int) -> list[tuple[int, int]]:
    rng = random.Random(seed)
    seen: set[tuple[int, int]] = set()
    while len(seen) < edges:
        u = rng.randrange(n)
        v = rng.randrange(n)
        if u == v:
            continue
        if u > v:
            u, v = v, u
        seen.add((u, v))
    return sorted(seen)


def make_graphs(n: int, edges: int, seed: int):
    pairs = edge_list(n, edges, seed)
    g_f = fnx.Graph()
    g_f.add_nodes_from(range(n))
    g_f.add_edges_from(pairs)
    g_n = nx.Graph()
    g_n.add_nodes_from(range(n))
    g_n.add_edges_from(pairs)
    return g_f, g_n


def strip_comments(payload: bytes) -> bytes:
    return b"".join(
        line for line in payload.splitlines(keepends=True) if not line.startswith(b"#")
    )


def write_once(graph, impl_name: str) -> bytes:
    output = io.BytesIO()
    if impl_name == "fnx":
        fnx.write_adjlist(graph, output)
    elif impl_name == "nx":
        nx.write_adjlist(graph, output)
    else:
        raise ValueError(impl_name)
    return output.getvalue()


def golden(n: int, edges: int, seed: int) -> dict:
    g_f, g_n = make_graphs(n, edges, seed)
    fnx_body = strip_comments(write_once(g_f, "fnx"))
    nx_body = strip_comments(write_once(g_n, "nx"))
    return {
        "n": n,
        "edges": edges,
        "seed": seed,
        "fnx_body_sha256": hashlib.sha256(fnx_body).hexdigest(),
        "nx_body_sha256": hashlib.sha256(nx_body).hexdigest(),
        "body_equal": fnx_body == nx_body,
        "body_size": len(fnx_body),
        "trailing_newline": fnx_body.endswith(b"\n"),
    }


def bench(impl_name: str, n: int, edges: int, seed: int, loops: int) -> dict:
    g_f, g_n = make_graphs(n, edges, seed)
    graph = g_f if impl_name == "fnx" else g_n
    started = time.perf_counter()
    total_bytes = 0
    for _ in range(loops):
        total_bytes += len(write_once(graph, impl_name))
    elapsed = time.perf_counter() - started
    return {
        "impl": impl_name,
        "n": n,
        "edges": edges,
        "seed": seed,
        "loops": loops,
        "elapsed_s": elapsed,
        "per_loop_s": elapsed / loops,
        "total_bytes": total_bytes,
    }


def profile(impl_name: str, n: int, edges: int, seed: int, loops: int, limit: int) -> str:
    profiler = cProfile.Profile()
    profiler.enable()
    bench(impl_name, n, edges, seed, loops)
    profiler.disable()
    output = StringIO()
    stats = pstats.Stats(profiler, stream=output).sort_stats("cumulative")
    stats.print_stats(limit)
    return output.getvalue()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=3000)
    parser.add_argument("--edges", type=int, default=9000)
    parser.add_argument("--seed", type=int, default=7)
    subcommands = parser.add_subparsers(dest="command", required=True)

    golden_parser = subcommands.add_parser("golden")
    golden_parser.set_defaults(func=lambda args: golden(args.n, args.edges, args.seed))

    bench_parser = subcommands.add_parser("bench")
    bench_parser.add_argument("--impl", choices=["fnx", "nx"], required=True)
    bench_parser.add_argument("--loops", type=int, default=20)
    bench_parser.set_defaults(
        func=lambda args: bench(args.impl, args.n, args.edges, args.seed, args.loops)
    )

    profile_parser = subcommands.add_parser("profile")
    profile_parser.add_argument("--impl", choices=["fnx", "nx"], required=True)
    profile_parser.add_argument("--loops", type=int, default=5)
    profile_parser.add_argument("--limit", type=int, default=50)
    profile_parser.set_defaults(
        func=lambda args: profile(
            args.impl, args.n, args.edges, args.seed, args.loops, args.limit
        )
    )

    args = parser.parse_args()
    result = args.func(args)
    if isinstance(result, str):
        print(result, end="")
    else:
        print(json.dumps(result, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
