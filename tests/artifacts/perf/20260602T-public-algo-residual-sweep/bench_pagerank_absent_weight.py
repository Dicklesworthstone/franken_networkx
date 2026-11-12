#!/usr/bin/env python3
"""Benchmark PageRank when the requested string weight attr is absent.

Mode ``old`` disables the new attr-absence proof at runtime so the command
exercises the pre-change route: sync attrs, scan for non-finite weights, and
build sparse adjacency with the string weight key. Mode ``new`` leaves the
current route enabled.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import time

import networkx as nx

import franken_networkx as fnx


def _digest(result: dict[object, float]) -> str:
    payload = json.dumps(
        [(repr(node), format(score, ".17g")) for node, score in result.items()],
        separators=(",", ":"),
    ).encode()
    return hashlib.sha256(payload).hexdigest()


def _measure(func, repeats: int) -> tuple[list[float], dict[object, float]]:
    samples = []
    result = {}
    for _ in range(repeats):
        start = time.perf_counter()
        result = func()
        samples.append(time.perf_counter() - start)
    return samples, result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--impl", choices=("fnx", "nx"), required=True)
    parser.add_argument("--mode", choices=("old", "new"), default="new")
    parser.add_argument("--n", type=int, default=1000)
    parser.add_argument("--p", type=float, default=0.05)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--repeats", type=int, default=7)
    args = parser.parse_args()

    nx_graph = nx.gnp_random_graph(args.n, args.p, seed=args.seed)
    if args.impl == "nx":
        graph = nx_graph
        module = nx
    else:
        graph = fnx.Graph()
        graph.add_nodes_from(nx_graph.nodes())
        graph.add_edges_from(nx_graph.edges())
        module = fnx
        if args.mode == "old":
            fnx._native_has_edge_attr = None

    module.pagerank(graph)
    samples, result = _measure(lambda: module.pagerank(graph), args.repeats)
    print(
        json.dumps(
            {
                "case": "pagerank_absent_weight",
                "impl": args.impl,
                "mode": args.mode,
                "n": args.n,
                "p": args.p,
                "seed": args.seed,
                "repeats": args.repeats,
                "mean_sec": statistics.fmean(samples),
                "median_sec": statistics.median(samples),
                "min_sec": min(samples),
                "max_sec": max(samples),
                "samples_sec": samples,
                "digest": _digest(result),
            },
            sort_keys=True,
            separators=(",", ":"),
        ),
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
