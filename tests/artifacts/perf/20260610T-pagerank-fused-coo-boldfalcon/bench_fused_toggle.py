#!/usr/bin/env python3
"""Same-binary PageRank benchmark with the fused helper enabled/disabled."""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import time

import franken_networkx as fnx


OFFSETS = (1, 7, 17, 31)


def build_graph(n: int):
    graph = fnx.DiGraph()
    graph.add_nodes_from(
        (
            i,
            {
                "payload": f"node-{i:05d}",
                "rank": i,
                "group": i % 17,
                "active": (i % 3) == 0,
                "label": f"group-{i % 17}",
                "score": (i % 101) / 101.0,
                "left": i - 1,
                "right": i + 1,
                "stamp": f"2026-06-10:{i % 60:02d}",
                "kind": "pagerank-fused-toggle",
                "odd": (i & 1) == 1,
                "mod7": i % 7,
            },
        )
        for i in range(n)
    )
    graph.add_edges_from(
        (
            i,
            (i + offset) % n,
            {"weight": ((i * 131 + offset * 17) % 97 + 1) / 97.0},
        )
        for i in range(n)
        for offset in OFFSETS
    )
    return graph


def canonical(result: dict[int, float]) -> str:
    rows = [(int(node), format(float(score), ".17g")) for node, score in result.items()]
    return json.dumps(rows, separators=(",", ":"))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("enabled", "disabled"), required=True)
    parser.add_argument("--n", type=int, default=1400)
    parser.add_argument("--loops", type=int, default=80)
    args = parser.parse_args()

    if args.mode == "disabled":
        fnx._native_pagerank_default_order_arrays_checked = None

    graph = build_graph(args.n)
    values = []
    result = fnx.pagerank(graph, weight="weight", tol=1e-8, max_iter=100)
    for _ in range(args.loops):
        start = time.perf_counter()
        result = fnx.pagerank(graph, weight="weight", tol=1e-8, max_iter=100)
        values.append(time.perf_counter() - start)

    payload = canonical(result)
    print(
        json.dumps(
            {
                "mode": args.mode,
                "n": args.n,
                "edges": len(OFFSETS) * args.n,
                "loops": args.loops,
                "median_s": statistics.median(values),
                "mean_s": statistics.fmean(values),
                "min_s": min(values),
                "max_s": max(values),
                "sha256": hashlib.sha256(payload.encode()).hexdigest(),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
