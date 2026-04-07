#!/usr/bin/env python3
"""Lightweight local benchmark comparison against NetworkX."""

from __future__ import annotations

import json
import os
import statistics
import time

import franken_networkx as fnx
import networkx as nx


RUNS = int(os.environ.get("FNX_BENCH_RUNS", "3"))
PATH_NODES = int(os.environ.get("FNX_BENCH_PATH_NODES", "2500"))
COMPONENT_NODES = int(os.environ.get("FNX_BENCH_COMPONENT_NODES", "1200"))
PAGERANK_NODES = int(os.environ.get("FNX_BENCH_PAGERANK_NODES", "180"))


def measure(func, runs: int) -> dict[str, float]:
    samples = []
    for _ in range(runs):
        start = time.perf_counter()
        func()
        samples.append((time.perf_counter() - start) * 1000.0)
    return {
        "median_ms": round(statistics.median(samples), 3),
        "min_ms": round(min(samples), 3),
        "max_ms": round(max(samples), 3),
    }


def speedup(fnx_stats: dict[str, float], nx_stats: dict[str, float]) -> float | None:
    baseline = nx_stats["median_ms"]
    if baseline == 0.0:
        return None
    return round(baseline / fnx_stats["median_ms"], 3)


def main() -> int:
    nx_path_graph = nx.path_graph(PATH_NODES)
    fnx_path_graph = fnx.path_graph(PATH_NODES)

    nx_component_graph = nx.gnp_random_graph(COMPONENT_NODES, 0.002, seed=7)
    fnx_component_graph = fnx.Graph()
    fnx_component_graph.add_edges_from(nx_component_graph.edges())

    nx_pagerank_graph = nx.barabasi_albert_graph(PAGERANK_NODES, 3, seed=11)
    fnx_pagerank_graph = fnx.Graph()
    fnx_pagerank_graph.add_edges_from(nx_pagerank_graph.edges())

    report = {
        "shortest_path": {
            "franken_networkx": measure(
                lambda: fnx.shortest_path(fnx_path_graph, 0, PATH_NODES - 1),
                RUNS,
            ),
            "networkx": measure(
                lambda: nx.shortest_path(nx_path_graph, 0, PATH_NODES - 1),
                RUNS,
            ),
        },
        "connected_components": {
            "franken_networkx": measure(
                lambda: list(fnx.connected_components(fnx_component_graph)),
                RUNS,
            ),
            "networkx": measure(
                lambda: list(nx.connected_components(nx_component_graph)),
                RUNS,
            ),
        },
        "pagerank": {
            "franken_networkx": measure(
                lambda: fnx.pagerank(fnx_pagerank_graph),
                RUNS,
            ),
            "networkx": measure(
                lambda: nx.pagerank(nx_pagerank_graph),
                RUNS,
            ),
        },
    }

    for name, entry in report.items():
        entry["speedup_vs_networkx"] = speedup(entry["franken_networkx"], entry["networkx"])

    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
