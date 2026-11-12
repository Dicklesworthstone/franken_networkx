#!/usr/bin/env python3
"""Timing and upstream-drift smoke for raw weighted Dijkstra.

The benchmark graph follows the bead target:
BA(2000, 4, seed=42), source=0, deterministic positive weights.

This script compares current fnx output with NetworkX as a diagnostic.
The behavior golden for this optimization is the old-fnx-vs-new-fnx
checksum pair in golden_sha256.txt.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import time
from typing import Any, Callable

import franken_networkx as fnx
import franken_networkx._fnx as raw
import networkx as nx


def weighted_ba(n: int, m: int, seed: int) -> tuple[Any, Any]:
    nx_graph = nx.barabasi_albert_graph(n, m, seed=seed)
    for i, (u, v) in enumerate(nx_graph.edges()):
        nx_graph[u][v]["weight"] = 1.0 + ((i * 17 + 11) % 23) / 10.0

    fnx_graph = fnx.Graph()
    fnx_graph.add_nodes_from(nx_graph.nodes(data=True))
    fnx_graph.add_edges_from((u, v, dict(attrs)) for u, v, attrs in nx_graph.edges(data=True))
    return fnx_graph, nx_graph


def digest(distances: dict[Any, float]) -> str:
    payload = json.dumps(
        [(repr(node), format(distance, ".17g")) for node, distance in distances.items()],
        separators=(",", ":"),
    ).encode()
    return hashlib.sha256(payload).hexdigest()


def compare_distances(left: dict[Any, float], right: dict[Any, float]) -> dict[str, Any]:
    keys_equal = set(left) == set(right)
    max_abs_diff = 0.0
    exact_diff_count = 0
    for node in left:
        diff = abs(left[node] - right[node])
        max_abs_diff = max(max_abs_diff, diff)
        if diff != 0.0:
            exact_diff_count += 1
    first_order_mismatch = next(
        (i for i, (left_node, right_node) in enumerate(zip(left, right)) if left_node != right_node),
        None,
    )
    return {
        "keys_equal": keys_equal,
        "max_abs_diff": max_abs_diff,
        "exact_diff_count": exact_diff_count,
        "allclose_abs_1e_12": keys_equal and max_abs_diff <= 1.0e-12,
        "first_order_mismatch_index": first_order_mismatch,
    }


def sample(label: str, repeats: int, call: Callable[[], dict[Any, float]]) -> dict[str, Any]:
    call()
    times: list[float] = []
    output: dict[Any, float] | None = None
    for _ in range(repeats):
        start = time.perf_counter()
        output = call()
        times.append(time.perf_counter() - start)
    assert output is not None
    return {
        "impl": label,
        "mean_seconds": statistics.fmean(times),
        "median_seconds": statistics.median(times),
        "min_seconds": min(times),
        "max_seconds": max(times),
        "sha256": digest(output),
        "size": len(output),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=2000)
    parser.add_argument("--m", type=int, default=4)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--source", type=int, default=0)
    parser.add_argument("--repeats", type=int, default=5)
    args = parser.parse_args()

    fnx_graph, nx_graph = weighted_ba(args.n, args.m, args.seed)
    fnx_output = raw.single_source_dijkstra_path_length(fnx_graph, args.source, weight="weight")
    nx_output = nx.single_source_dijkstra_path_length(nx_graph, args.source, weight="weight")
    comparison = compare_distances(fnx_output, nx_output)
    fnx_result = sample(
        "fnx_raw",
        args.repeats,
        lambda: raw.single_source_dijkstra_path_length(fnx_graph, args.source, weight="weight"),
    )
    nx_result = sample(
        "networkx",
        args.repeats,
        lambda: nx.single_source_dijkstra_path_length(nx_graph, args.source, weight="weight"),
    )
    print(
        json.dumps(
            {
                "case": "single_source_dijkstra_path_length_weighted_ba",
                "n": args.n,
                "m": args.m,
                "seed": args.seed,
                "source": args.source,
                "repeats": args.repeats,
                "fnx": fnx_result,
                "nx": nx_result,
                "exact_sha_equal": fnx_result["sha256"] == nx_result["sha256"],
                "distance_comparison": comparison,
                "golden_contract": "old_fnx_loop_vs_new_fnx_loop; see golden_sha256.txt",
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
