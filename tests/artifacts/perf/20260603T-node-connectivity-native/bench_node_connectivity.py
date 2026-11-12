#!/usr/bin/env python3
"""Profile node_connectivity on deterministic deg-bounded graph families."""

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


def build_reciprocal_ring_edges(n: int, extra_per_node: int, seed: int):
    edges = []
    for node in range(n):
        edges.append((node, (node + 1) % n))
        edges.append(((node + 1) % n, node))

    rng = random.Random(seed)
    seen = set(edges)
    for node in range(n):
        added = 0
        while added < extra_per_node:
            target = rng.randrange(n)
            if target == node:
                continue
            edge = (node, target)
            if edge in seen:
                continue
            seen.add(edge)
            edges.append(edge)
            added += 1
    return edges


def build_directed_chord_edges(n: int, degree: int):
    edges = []
    for node in range(n):
        for offset in range(1, degree + 1):
            edges.append((node, (node + offset) % n))
    return edges


def build_gnm_ring_edges(n: int, degree: int, seed: int):
    edge_target = n * degree
    edges = build_directed_chord_edges(n, 1)
    seen = set(edges)
    graph = nx.gnm_random_graph(n, edge_target, seed=seed, directed=True)
    for edge in graph.edges():
        if edge[0] != edge[1] and edge not in seen:
            seen.add(edge)
            edges.append(edge)
    return edges


def build_regular_to_directed_edges(n: int, degree: int, seed: int):
    graph = nx.random_regular_graph(degree, n, seed=seed)
    edges = []
    for left, right in graph.edges():
        edges.append((left, right))
        edges.append((right, left))
    return edges


def build_regular_edges(n: int, degree: int, seed: int):
    graph = nx.random_regular_graph(degree, n, seed=seed)
    return list(graph.edges())


def build_edges(mode: str, n: int, degree: int, seed: int):
    if mode == "reciprocal-ring":
        return build_reciprocal_ring_edges(n, max(0, degree - 2), seed)
    if mode == "directed-chord":
        return build_directed_chord_edges(n, degree)
    if mode == "gnm-ring":
        return build_gnm_ring_edges(n, degree, seed)
    if mode == "regular-to-directed":
        return build_regular_to_directed_edges(n, degree, seed)
    if mode == "regular":
        return build_regular_edges(n, degree, seed)
    raise ValueError(f"unknown mode: {mode}")


def build_graph(module, kind: str, mode: str, n: int, degree: int, seed: int):
    graph = module.Graph() if kind == "graph" else module.DiGraph()
    graph.add_nodes_from(range(n))
    graph.add_edges_from(build_edges(mode, n, degree, seed))
    return graph


def digest_result(value: int, graph) -> str:
    payload = {
        "value": value,
        "nodes": list(graph.nodes())[:20],
        "edges": list(graph.edges())[:40],
        "node_count": graph.number_of_nodes(),
        "edge_count": graph.number_of_edges(),
    }
    encoded = json.dumps(payload, sort_keys=True, default=repr).encode()
    return hashlib.sha256(encoded).hexdigest()


def run_case(
    engine: str,
    kind: str,
    mode: str,
    n: int,
    degree: int,
    seed: int,
    *,
    digest: bool,
):
    module = fnx if engine == "fnx" else nx
    graph = build_graph(module, kind, mode, n, degree, seed)

    started = time.perf_counter()
    value = module.node_connectivity(graph)
    elapsed = time.perf_counter() - started

    row = {
        "engine": engine,
        "elapsed": elapsed,
        "value": value,
        "node_count": graph.number_of_nodes(),
        "edge_count": graph.number_of_edges(),
    }
    if digest:
        row["digest"] = digest_result(value, graph)
    return row


def command_bench(args):
    rows = []
    for engine in args.engines:
        samples = [
            run_case(
                engine,
                args.kind,
                args.mode,
                args.n,
                args.degree,
                args.seed,
                digest=not args.skip_digest,
            )
            for _ in range(args.samples)
        ]
        row = {
            "engine": engine,
            "samples": samples,
            "mean": sum(sample["elapsed"] for sample in samples) / len(samples),
            "value": samples[-1]["value"],
            "node_count": samples[-1]["node_count"],
            "edge_count": samples[-1]["edge_count"],
        }
        if not args.skip_digest:
            row["digest"] = samples[-1]["digest"]
        rows.append(row)
    print(
        json.dumps(
            {
                "case": {
                    "kind": args.kind,
                    "mode": args.mode,
                    "n": args.n,
                    "degree": args.degree,
                    "seed": args.seed,
                    "samples": args.samples,
                    "engines": args.engines,
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
        "fnx",
        args.kind,
        args.mode,
        args.n,
        args.degree,
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
    bench.add_argument(
        "--mode",
        choices=(
            "reciprocal-ring",
            "directed-chord",
            "gnm-ring",
            "regular",
            "regular-to-directed",
        ),
        default="gnm-ring",
    )
    bench.add_argument("--kind", choices=("graph", "digraph"), default="digraph")
    bench.add_argument("--n", type=int, default=400)
    bench.add_argument("--degree", type=int, default=4)
    bench.add_argument("--seed", type=int, default=8675309)
    bench.add_argument("--samples", type=int, default=1)
    bench.add_argument(
        "--engines",
        nargs="+",
        choices=("fnx", "nx"),
        default=["fnx", "nx"],
    )
    bench.add_argument("--skip-digest", action="store_true")
    bench.set_defaults(func=command_bench)

    profile = subparsers.add_parser("profile")
    profile.add_argument(
        "--mode",
        choices=(
            "reciprocal-ring",
            "directed-chord",
            "gnm-ring",
            "regular",
            "regular-to-directed",
        ),
        default="gnm-ring",
    )
    profile.add_argument("--kind", choices=("graph", "digraph"), default="digraph")
    profile.add_argument("--n", type=int, default=400)
    profile.add_argument("--degree", type=int, default=4)
    profile.add_argument("--seed", type=int, default=8675309)
    profile.add_argument("--output", required=True)
    profile.add_argument("--limit", type=int, default=50)
    profile.add_argument("--skip-digest", action="store_true")
    profile.set_defaults(func=command_profile)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
