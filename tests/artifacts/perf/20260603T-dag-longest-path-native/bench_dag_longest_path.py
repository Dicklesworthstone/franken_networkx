#!/usr/bin/env python3
"""Benchmark dag_longest_path legacy and native-fast-path modes."""

from __future__ import annotations

import argparse
import cProfile
import hashlib
import io
import json
import pstats
import random
import time
from pathlib import Path

import franken_networkx as fnx
import networkx as nx


def build_edges(n: int, edge_count: int, seed: int):
    rng = random.Random(seed)
    seen = set()
    edges = []
    while len(edges) < edge_count:
        left = rng.randrange(n - 1)
        right = rng.randrange(left + 1, n)
        edge = (left, right)
        if edge in seen:
            continue
        seen.add(edge)
        edges.append(edge)
    edges.sort()
    return edges


def build_graph(module, n: int, edge_count: int, seed: int):
    graph = module.DiGraph()
    graph.add_nodes_from(range(n))
    graph.add_edges_from(build_edges(n, edge_count, seed))
    return graph


def dag_longest_path_native_list(graph):
    topo_order = list(fnx.topological_sort(graph))
    pred_map = {node: [] for node in topo_order}
    for u, v, edge_weight in graph._native_in_edges_data_key("weight", 1):
        pred_map[v].append((u, edge_weight))

    dist = {}
    for v in topo_order:
        us = [
            (dist[u][0] + edge_weight, u)
            for u, edge_weight in pred_map[v]
        ]
        maxu = max(us, key=lambda x: x[0]) if us else (0, v)
        dist[v] = maxu if maxu[0] >= 0 else (0, v)

    u = None
    v = max(dist, key=lambda x: dist[x][0])
    path = []
    while u != v:
        path.append(v)
        u = v
        v = dist[v][1]
    path.reverse()
    return path


def digest_result(path, graph) -> str:
    payload = {
        "path": list(path),
        "nodes": list(graph.nodes())[:20],
        "edges": list(graph.edges())[:40],
        "node_count": graph.number_of_nodes(),
        "edge_count": graph.number_of_edges(),
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def run_case(engine: str, n: int, edge_count: int, seed: int, *, digest: bool):
    module = nx if engine == "nx" else fnx
    graph = build_graph(module, n, edge_count, seed)

    started = time.perf_counter()
    if engine == "fnx-legacy":
        topo_order = list(fnx.topological_sort(graph))
        path = fnx.dag_longest_path(graph, topo_order=topo_order)
    elif engine == "fnx-native-list":
        path = dag_longest_path_native_list(graph)
    else:
        path = module.dag_longest_path(graph)
    elapsed = time.perf_counter() - started

    row = {
        "edge_count": graph.number_of_edges(),
        "elapsed": elapsed,
        "engine": engine,
        "node_count": graph.number_of_nodes(),
        "path": list(path),
        "path_len": len(path),
    }
    if digest:
        row["digest"] = digest_result(path, graph)
    return row


def command_bench(args):
    rows = []
    for engine in args.engines:
        samples = [
            run_case(
                engine,
                args.n,
                args.edge_count,
                args.seed,
                digest=not args.skip_digest,
            )
            for _ in range(args.samples)
        ]
        row = {
            "digest": samples[-1].get("digest"),
            "edge_count": samples[-1]["edge_count"],
            "engine": engine,
            "mean": sum(sample["elapsed"] for sample in samples) / len(samples),
            "node_count": samples[-1]["node_count"],
            "path": samples[-1]["path"],
            "path_len": samples[-1]["path_len"],
            "samples": samples,
        }
        rows.append(row)
    print(
        json.dumps(
            {
                "case": {
                    "edge_count": args.edge_count,
                    "engines": args.engines,
                    "n": args.n,
                    "samples": args.samples,
                    "seed": args.seed,
                },
                "rows": rows,
            },
            sort_keys=True,
        )
    )


def command_profile(args):
    profiler = cProfile.Profile()
    profiler.enable()
    result = run_case(
        args.engine,
        args.n,
        args.edge_count,
        args.seed,
        digest=not args.skip_digest,
    )
    profiler.disable()

    stream = io.StringIO()
    pstats.Stats(profiler, stream=stream).sort_stats("cumtime").print_stats(
        args.limit
    )
    Path(args.output).write_text(stream.getvalue())
    print(json.dumps({"profile": args.output, "result": result}, sort_keys=True))


def main():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    bench = subparsers.add_parser("bench")
    bench.add_argument("--n", type=int, default=400)
    bench.add_argument("--edge-count", type=int, default=1600)
    bench.add_argument("--seed", type=int, default=8675309)
    bench.add_argument("--samples", type=int, default=1)
    bench.add_argument(
        "--engines",
        nargs="+",
        choices=("fnx-legacy", "fnx-native-list", "fnx-native", "nx"),
        default=["fnx-legacy", "fnx-native", "nx"],
    )
    bench.add_argument("--skip-digest", action="store_true")
    bench.set_defaults(func=command_bench)

    profile = subparsers.add_parser("profile")
    profile.add_argument("--n", type=int, default=400)
    profile.add_argument("--edge-count", type=int, default=1600)
    profile.add_argument("--seed", type=int, default=8675309)
    profile.add_argument(
        "--engine",
        choices=("fnx-legacy", "fnx-native-list", "fnx-native", "nx"),
        default="fnx-legacy",
    )
    profile.add_argument("--output", required=True)
    profile.add_argument("--limit", type=int, default=50)
    profile.add_argument("--skip-digest", action="store_true")
    profile.set_defaults(func=command_profile)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
