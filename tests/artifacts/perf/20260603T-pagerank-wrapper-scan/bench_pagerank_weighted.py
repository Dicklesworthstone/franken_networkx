#!/usr/bin/env python3
"""Weighted PageRank benchmark for br-r37-c1-dptts."""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import time
from typing import Any

import franken_networkx as fnx
import networkx as nx


def build_pair(n: int, m: int, seed: int) -> tuple[Any, Any]:
    base = nx.barabasi_albert_graph(n, m, seed=seed)
    for index, (u, v) in enumerate(base.edges()):
        base[u][v]["weight"] = 1.0 + ((index * 17 + 11) % 23) / 10.0

    rust_graph = fnx.Graph()
    rust_graph.add_nodes_from(base.nodes(data=True))
    rust_graph.add_edges_from((u, v, dict(attrs)) for u, v, attrs in base.edges(data=True))
    return rust_graph, base


def digest(result: dict[Any, float]) -> str:
    payload = json.dumps(
        [(repr(node), format(score, ".17g")) for node, score in result.items()],
        separators=(",", ":"),
    ).encode()
    return hashlib.sha256(payload).hexdigest()


def sample(impl: str, repeats: int, n: int, m: int, seed: int) -> dict[str, Any]:
    graph_f, graph_n = build_pair(n, m, seed)
    module = fnx if impl == "fnx" else nx
    graph = graph_f if impl == "fnx" else graph_n
    durations: list[float] = []
    result: dict[Any, float] = {}

    module.pagerank(graph, weight="weight")
    for _ in range(repeats):
        start = time.perf_counter()
        result = module.pagerank(graph, weight="weight")
        durations.append(time.perf_counter() - start)

    ordered = sorted(durations)
    return {
        "case": "pagerank_weighted_ba",
        "impl": impl,
        "n": n,
        "m": m,
        "seed": seed,
        "repeats": repeats,
        "mean_seconds": statistics.fmean(durations),
        "median_seconds": statistics.median(durations),
        "min_seconds": ordered[0],
        "max_seconds": ordered[-1],
        "sha256": digest(result),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--impl", choices=("fnx", "nx"), required=True)
    parser.add_argument("--repeats", type=int, default=7)
    parser.add_argument("--n", type=int, default=2000)
    parser.add_argument("--m", type=int, default=4)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    print(
        json.dumps(
            sample(args.impl, args.repeats, args.n, args.m, args.seed),
            sort_keys=True,
            separators=(",", ":"),
        )
    )


if __name__ == "__main__":
    main()
