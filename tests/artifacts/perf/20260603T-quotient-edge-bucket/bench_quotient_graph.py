#!/usr/bin/env python3
"""Profile and verify the quotient_graph default edge-relation path."""

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


def build_graph(graph_cls, n: int, block_size: int, extra_edges: int):
    graph = graph_cls()
    graph.add_nodes_from(range(n))

    for start in range(0, n - block_size, block_size):
        graph.add_edge(start + block_size - 1, start + block_size)

    rng = random.Random(12345)
    for _ in range(extra_edges):
        u = rng.randrange(n)
        v = rng.randrange(n)
        if u != v:
            graph.add_edge(u, v)

    return graph


def make_partition(n: int, block_size: int):
    return [set(range(start, min(start + block_size, n))) for start in range(0, n, block_size)]


def canonical_edges(graph):
    payload = []
    for u, v, data in graph.edges(data=True):
        payload.append(
            {
                "u": sorted(u),
                "v": sorted(v),
                "attrs": sorted(data.items()),
            }
        )
    return payload


def canonical_nodes(graph):
    payload = []
    for node, data in graph.nodes(data=True):
        payload.append(
            {
                "node": sorted(node) if isinstance(node, frozenset) else node,
                "nnodes": data.get("nnodes"),
                "nedges": data.get("nedges"),
                "density": data.get("density"),
            }
        )
    return payload


def digest_result(graph):
    payload = {
        "nodes": canonical_nodes(graph),
        "edges": canonical_edges(graph),
    }
    encoded = json.dumps(payload, sort_keys=True, default=repr).encode()
    return hashlib.sha256(encoded).hexdigest(), payload


def run_case(engine: str, n: int, block_size: int, extra_edges: int):
    module = fnx if engine == "fnx" else nx
    graph_cls = fnx.Graph if engine == "fnx" else nx.Graph
    graph = build_graph(graph_cls, n, block_size, extra_edges)
    partition = make_partition(n, block_size)

    started = time.perf_counter()
    quotient = module.quotient_graph(graph, partition)
    elapsed = time.perf_counter() - started

    digest, payload = digest_result(quotient)
    return {
        "engine": engine,
        "elapsed": elapsed,
        "digest": digest,
        "node_count": quotient.number_of_nodes(),
        "edge_count": quotient.number_of_edges(),
        "first_edges": payload["edges"][:12],
    }


def command_bench(args):
    case = {
        "n": args.n,
        "block_size": args.block_size,
        "extra_edges": args.extra_edges,
        "samples": args.samples,
        "engines": args.engines,
    }
    rows = []
    for engine in args.engines:
        samples = [
            run_case(engine, args.n, args.block_size, args.extra_edges)
            for _ in range(args.samples)
        ]
        rows.append(
            {
                "engine": engine,
                "samples": samples,
                "mean": sum(sample["elapsed"] for sample in samples) / len(samples),
                "digest": samples[-1]["digest"],
                "node_count": samples[-1]["node_count"],
                "edge_count": samples[-1]["edge_count"],
                "first_edges": samples[-1]["first_edges"],
            }
        )
    print(json.dumps({"case": case, "rows": rows}, sort_keys=True))


def command_profile(args):
    profiler = cProfile.Profile()
    profiler.enable()
    result = run_case("fnx", args.n, args.block_size, args.extra_edges)
    profiler.disable()

    stream = io.StringIO()
    pstats.Stats(profiler, stream=stream).sort_stats("cumtime").print_stats(args.limit)
    Path(args.output).write_text(stream.getvalue())
    print(json.dumps({"profile": args.output, "result": result}, sort_keys=True))


def main():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    bench = subparsers.add_parser("bench")
    bench.add_argument("--n", type=int, default=3000)
    bench.add_argument("--block-size", type=int, default=10)
    bench.add_argument("--extra-edges", type=int, default=9000)
    bench.add_argument("--samples", type=int, default=1)
    bench.add_argument("--engines", nargs="+", choices=("fnx", "nx"), default=["fnx", "nx"])
    bench.set_defaults(func=command_bench)

    profile = subparsers.add_parser("profile")
    profile.add_argument("--n", type=int, default=3000)
    profile.add_argument("--block-size", type=int, default=10)
    profile.add_argument("--extra-edges", type=int, default=9000)
    profile.add_argument("--output", required=True)
    profile.add_argument("--limit", type=int, default=40)
    profile.set_defaults(func=command_profile)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
