#!/usr/bin/env python3
"""Perf harness for br-r37-c1-6nzsy.

Builds one deterministic connected sparse weighted graph and executes repeated
single-pair bidirectional Dijkstra queries. Kept as an artifact so baseline and
after hyperfine runs use the same workload.
"""

from __future__ import annotations

import argparse
import random

import franken_networkx as fnx
import networkx as nx

N = 3000
M = 12000
SEED = 613
PAIRS = [(0, 2999), (17, 2199), (123, 2501), (700, 1700), (42, 2048), (900, 2800)]


def edge_weight(u: int, v: int) -> int:
    return ((u * 1103515245 + v * 12345 + 97) & 1023) + 1


def deterministic_edges() -> list[tuple[int, int]]:
    rng = random.Random(SEED)
    edges = {(i, i + 1) for i in range(N - 1)}
    while len(edges) < M:
        u = rng.randrange(N)
        v = rng.randrange(N)
        if u == v:
            continue
        if u > v:
            u, v = v, u
        edges.add((u, v))
    return sorted(edges)


def build_graph(module):
    graph = module.Graph()
    graph.add_nodes_from(range(N))
    for u, v in deterministic_edges():
        graph.add_edge(u, v, weight=edge_weight(u, v))
    return graph


def run_public(loops: int) -> None:
    graph = build_graph(fnx)
    for i in range(loops):
        source, target = PAIRS[i % len(PAIRS)]
        fnx.bidirectional_dijkstra(graph, source, target, weight="weight")


def run_public_nocache(loops: int) -> None:
    graph = build_graph(fnx)
    fnx._native_dijkstra_weight_cache_token = None
    for i in range(loops):
        source, target = PAIRS[i % len(PAIRS)]
        fnx.bidirectional_dijkstra(graph, source, target, weight="weight")


def run_native_check(loops: int) -> None:
    graph = build_graph(fnx)
    for _ in range(loops):
        fnx._native_check_dijkstra_weights_fast(graph, "weight")


def run_native_kernel(loops: int) -> None:
    graph = build_graph(fnx)
    fnx._sync_rust_edge_attrs(graph, edge_only=True)
    for i in range(loops):
        source, target = PAIRS[i % len(PAIRS)]
        fnx._native_bidirectional_dijkstra(graph, source, target, "weight")


def run_networkx(loops: int) -> None:
    graph = build_graph(nx)
    for i in range(loops):
        source, target = PAIRS[i % len(PAIRS)]
        nx.bidirectional_dijkstra(graph, source, target, weight="weight")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode",
        choices=("public", "public-nocache", "native-check", "native-kernel", "networkx"),
        required=True,
    )
    parser.add_argument("--loops", type=int, default=100)
    args = parser.parse_args()

    if args.mode == "public":
        run_public(args.loops)
    elif args.mode == "public-nocache":
        run_public_nocache(args.loops)
    elif args.mode == "native-check":
        run_native_check(args.loops)
    elif args.mode == "native-kernel":
        run_native_kernel(args.loops)
    else:
        run_networkx(args.loops)


if __name__ == "__main__":
    main()
