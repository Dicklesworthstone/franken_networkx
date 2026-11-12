#!/usr/bin/env python3
"""Benchmark and golden harness for DiGraph.edges materialization."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import statistics
import time

import franken_networkx as fnx
import networkx as nx


def make_edges(n: int, m: int, seed: int) -> list[tuple[int, int]]:
    rng = random.Random(seed)
    seen: set[tuple[int, int]] = set()
    edges: list[tuple[int, int]] = []
    while len(edges) < m:
        u = rng.randrange(n)
        v = rng.randrange(n)
        if u == v:
            continue
        edge = (u, v)
        if edge in seen:
            continue
        seen.add(edge)
        edges.append(edge)
    return edges


def build_graph(module, n: int, m: int, seed: int):
    graph = module.DiGraph()
    graph.add_nodes_from(range(n))
    for idx, (u, v) in enumerate(make_edges(n, m, seed)):
        graph.add_edge(u, v, weight=idx, tag=f"e{idx % 17}")
    return graph


def edge_digest(edges: list[tuple[int, int]]) -> str:
    payload = json.dumps(edges, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def data_edge_digest(edges: list[tuple[int, int, dict]]) -> str:
    payload = json.dumps(edges, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def command_bench(args: argparse.Namespace) -> None:
    graph = build_graph(fnx, args.nodes, args.edges, args.seed)
    for _ in range(args.warmup):
        list(graph.edges())

    samples: list[float] = []
    checksum = 0
    edge_count = 0
    for _ in range(args.samples):
        start = time.perf_counter()
        for _ in range(args.iters):
            edges = list(graph.edges())
            edge_count = len(edges)
            checksum ^= len(edges)
            if edges:
                checksum ^= edges[0][0] * 1_000_003 + edges[-1][1]
        samples.append(time.perf_counter() - start)

    per_iter = [sample / args.iters for sample in samples]
    result = {
        "mode": "bench",
        "nodes": args.nodes,
        "edges": args.edges,
        "seed": args.seed,
        "samples": args.samples,
        "iters": args.iters,
        "edge_count": edge_count,
        "mean_s": statistics.mean(per_iter),
        "median_s": statistics.median(per_iter),
        "min_s": min(per_iter),
        "checksum": checksum,
    }
    print(json.dumps(result, sort_keys=True))


def command_golden(args: argparse.Namespace) -> None:
    fnx_graph = build_graph(fnx, args.nodes, args.edges, args.seed)
    nx_graph = build_graph(nx, args.nodes, args.edges, args.seed)

    fnx_edges = list(fnx_graph.edges())
    nx_edges = list(nx_graph.edges())
    fnx_data_edges = list(fnx_graph.edges(data=True))
    nx_data_edges = list(nx_graph.edges(data=True))

    if fnx_edges != nx_edges:
        raise AssertionError("fnx edge order differs from networkx")
    if fnx_data_edges != nx_data_edges:
        raise AssertionError("fnx data edge order differs from networkx")

    payload = {
        "nodes": args.nodes,
        "edges": args.edges,
        "seed": args.seed,
        "edge_digest": edge_digest(fnx_edges),
        "data_edge_digest": data_edge_digest(fnx_data_edges),
        "first_edges": fnx_edges[:20],
        "last_edges": fnx_edges[-20:],
        "first_data_edges": fnx_data_edges[:10],
        "last_data_edges": fnx_data_edges[-10:],
    }
    print(json.dumps(payload, sort_keys=True, separators=(",", ":")))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("bench", "golden"), required=True)
    parser.add_argument("--nodes", type=int, default=1800)
    parser.add_argument("--edges", type=int, default=9000)
    parser.add_argument("--seed", type=int, default=23)
    parser.add_argument("--samples", type=int, default=7)
    parser.add_argument("--iters", type=int, default=20)
    parser.add_argument("--warmup", type=int, default=3)
    args = parser.parse_args()

    if args.mode == "bench":
        command_bench(args)
    else:
        command_golden(args)


if __name__ == "__main__":
    main()
