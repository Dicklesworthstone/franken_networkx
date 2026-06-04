#!/usr/bin/env python3
"""Benchmark maximal_independent_set for br-r37-c1-dxm71."""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import time

import franken_networkx as fnx
import networkx as nx


def _digest(result: list[object]) -> str:
    payload = json.dumps([repr(node) for node in result], separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def _is_independent(graph, nodes: list[object]) -> bool:
    node_set = set(nodes)
    return all(v not in node_set for u in node_set for v in graph[u])


def _is_maximal(graph, nodes: list[object]) -> bool:
    node_set = set(nodes)
    return all(node in node_set or any(nbr in node_set for nbr in graph[node]) for node in graph)


def _build_graphs(n: int, m: int, seed: int):
    nx_graph = nx.barabasi_albert_graph(n, m, seed=seed)
    fnx_graph = fnx.Graph()
    fnx_graph.add_nodes_from(nx_graph.nodes())
    fnx_graph.add_edges_from(nx_graph.edges())
    return fnx_graph, nx_graph


def _measure(func, repeats: int) -> tuple[list[float], list[object]]:
    samples = []
    result: list[object] = []
    for _ in range(repeats):
        start = time.perf_counter()
        result = func()
        samples.append(time.perf_counter() - start)
    return samples, result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--impl", choices=("fnx", "nx"), required=True)
    parser.add_argument("--nodes", type=int, default=3000)
    parser.add_argument("--m", type=int, default=4)
    parser.add_argument("--graph-seed", type=int, default=42)
    parser.add_argument("--mis-seed", type=int, default=1)
    parser.add_argument("--repeats", type=int, default=9)
    args = parser.parse_args()

    fnx_graph, nx_graph = _build_graphs(args.nodes, args.m, args.graph_seed)
    if args.impl == "fnx":
        graph = fnx_graph
        module = fnx
    else:
        graph = nx_graph
        module = nx

    module.maximal_independent_set(graph, seed=args.mis_seed)
    samples, result = _measure(
        lambda: module.maximal_independent_set(graph, seed=args.mis_seed),
        args.repeats,
    )
    print(
        json.dumps(
            {
                "case": "maximal_independent_set_ba",
                "digest": _digest(result),
                "edges": graph.number_of_edges(),
                "graph_seed": args.graph_seed,
                "impl": args.impl,
                "independent": _is_independent(graph, result),
                "m": args.m,
                "maximal": _is_maximal(graph, result),
                "max_sec": max(samples),
                "mean_sec": statistics.fmean(samples),
                "median_sec": statistics.median(samples),
                "min_sec": min(samples),
                "mis_seed": args.mis_seed,
                "nodes": args.nodes,
                "result_len": len(result),
                "samples_sec": samples,
            },
            sort_keys=True,
            separators=(",", ":"),
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
