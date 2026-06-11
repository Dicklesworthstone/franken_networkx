#!/usr/bin/env python3
"""Benchmark and parity harness for br-r37-c1-tp7j4 generator work."""

from __future__ import annotations

import argparse
import cProfile
import hashlib
import json
import pstats
import statistics
import time
from pathlib import Path
from typing import Any, Callable

import franken_networkx as fnx
import networkx as nx


Scenario = tuple[str, Callable[[Any], Any]]


SCENARIOS: dict[str, Scenario] = {
    "star_5000": ("star_graph(5000)", lambda mod: mod.star_graph(5000)),
    "wheel_3000": ("wheel_graph(3000)", lambda mod: mod.wheel_graph(3000)),
    "full_rary_2_8191": ("full_rary_tree(2, 8191)", lambda mod: mod.full_rary_tree(2, 8191)),
    "balanced_2_12": ("balanced_tree(2, 12)", lambda mod: mod.balanced_tree(2, 12)),
    "circular_ladder_2000": (
        "circular_ladder_graph(2000)",
        lambda mod: mod.circular_ladder_graph(2000),
    ),
    "turan_300_5": ("turan_graph(300, 5)", lambda mod: mod.turan_graph(300, 5)),
    "caveman_50_50": ("caveman_graph(50, 50)", lambda mod: mod.caveman_graph(50, 50)),
    "lollipop_500_500": ("lollipop_graph(500, 500)", lambda mod: mod.lollipop_graph(500, 500)),
    "random_regular_8_1500": (
        "random_regular_graph(8, 1500, seed=12345)",
        lambda mod: mod.random_regular_graph(8, 1500, seed=12345),
    ),
}


def graph_payload(graph: Any) -> dict[str, Any]:
    nodes = list(graph.nodes(data=True))
    adjacency = []
    for node in graph:
        row = []
        for nbr, attrs in graph.adj[node].items():
            row.append([repr(nbr), sorted((repr(k), repr(v)) for k, v in attrs.items())])
        adjacency.append([repr(node), row])
    edges = []
    for edge in graph.edges(data=True):
        u, v, attrs = edge
        edges.append([repr(u), repr(v), sorted((repr(k), repr(vv)) for k, vv in attrs.items())])
    return {
        "nodes": [[repr(node), sorted((repr(k), repr(v)) for k, v in attrs.items())] for node, attrs in nodes],
        "adjacency": adjacency,
        "edges": edges,
        "node_count": graph.number_of_nodes(),
        "edge_count": graph.number_of_edges(),
    }


def digest_graph(graph: Any) -> str:
    payload = graph_payload(graph)
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(blob).hexdigest()


def build(engine: str, scenario: str) -> Any:
    _, factory = SCENARIOS[scenario]
    module = fnx if engine == "fnx" else nx
    return factory(module)


def bench(args: argparse.Namespace) -> None:
    times: list[float] = []
    last_digest = ""
    for _ in range(args.warmups):
        build(args.engine, args.scenario)
    for _ in range(args.samples):
        start = time.perf_counter()
        graph = build(args.engine, args.scenario)
        elapsed = time.perf_counter() - start
        if args.digest:
            last_digest = digest_graph(graph)
        times.append(elapsed)
    ordered = sorted(times)
    result = {
        "scenario": args.scenario,
        "label": SCENARIOS[args.scenario][0],
        "engine": args.engine,
        "samples": args.samples,
        "median_s": statistics.median(times),
        "mean_s": statistics.mean(times),
        "min_s": min(times),
        "p95_s": ordered[min(len(ordered) - 1, int(len(ordered) * 0.95))],
        "digest": last_digest,
    }
    print(json.dumps(result, sort_keys=True))


def proof(args: argparse.Namespace) -> None:
    cases = args.scenarios or list(SCENARIOS)
    results = []
    for scenario in cases:
        fnx_graph = build("fnx", scenario)
        nx_graph = build("nx", scenario)
        fnx_payload = graph_payload(fnx_graph)
        nx_payload = graph_payload(nx_graph)
        fnx_digest = digest_graph(fnx_graph)
        nx_digest = digest_graph(nx_graph)
        results.append(
            {
                "scenario": scenario,
                "label": SCENARIOS[scenario][0],
                "fnx_digest": fnx_digest,
                "nx_digest": nx_digest,
                "matches_nx": fnx_payload == nx_payload,
                "fnx_node_count": fnx_payload["node_count"],
                "nx_node_count": nx_payload["node_count"],
                "fnx_edge_count": fnx_payload["edge_count"],
                "nx_edge_count": nx_payload["edge_count"],
            }
        )
    payload = {"results": results, "all_match": all(row["matches_nx"] for row in results)}
    print(json.dumps(payload, sort_keys=True, indent=2))


def profile(args: argparse.Namespace) -> None:
    output = Path(args.output)
    stats_path = output.with_suffix(".prof")
    profiler = cProfile.Profile()
    for _ in range(args.warmups):
        build(args.engine, args.scenario)
    profiler.enable()
    for _ in range(args.samples):
        build(args.engine, args.scenario)
    profiler.disable()
    profiler.dump_stats(stats_path)
    with output.open("w", encoding="utf-8") as fh:
        stats = pstats.Stats(profiler, stream=fh)
        stats.strip_dirs().sort_stats("cumtime").print_stats(args.limit)


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)

    bench_parser = sub.add_parser("bench")
    bench_parser.add_argument("--engine", choices=["fnx", "nx"], required=True)
    bench_parser.add_argument("--scenario", choices=sorted(SCENARIOS), required=True)
    bench_parser.add_argument("--samples", type=int, default=25)
    bench_parser.add_argument("--warmups", type=int, default=5)
    bench_parser.add_argument("--digest", action="store_true")
    bench_parser.set_defaults(func=bench)

    proof_parser = sub.add_parser("proof")
    proof_parser.add_argument("--scenarios", nargs="*", choices=sorted(SCENARIOS))
    proof_parser.set_defaults(func=proof)

    profile_parser = sub.add_parser("profile")
    profile_parser.add_argument("--engine", choices=["fnx", "nx"], required=True)
    profile_parser.add_argument("--scenario", choices=sorted(SCENARIOS), required=True)
    profile_parser.add_argument("--samples", type=int, default=10)
    profile_parser.add_argument("--warmups", type=int, default=2)
    profile_parser.add_argument("--output", required=True)
    profile_parser.add_argument("--limit", type=int, default=40)
    profile_parser.set_defaults(func=profile)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
