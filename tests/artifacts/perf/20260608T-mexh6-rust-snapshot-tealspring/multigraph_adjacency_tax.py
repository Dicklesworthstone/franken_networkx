#!/usr/bin/env python3
"""Focused proof and timing harness for br-r37-c1-mexh6."""

from __future__ import annotations

import argparse
import cProfile
import hashlib
import json
import pstats
import statistics
import time
from pathlib import Path

import franken_networkx as fnx
import networkx as nx


def edge_stream(n: int = 1200, m: int = 6000):
    for i in range(m):
        u = (i * 37 + 11) % n
        v = (i * 91 + 17) % n
        key = i % 3
        data = {"weight": float((i % 17) + 1), "label": f"e{i % 29}"}
        yield u, v, key, data


def build_graph(module, graph_name: str, n: int = 1200, m: int = 6000):
    graph_type = getattr(module, graph_name)
    graph = graph_type()
    graph.add_nodes_from(range(n))
    for u, v, key, data in edge_stream(n, m):
        graph.add_edge(u, v, key=key, **data)
    return graph


def stable_value(value):
    if isinstance(value, dict):
        return [(stable_value(k), stable_value(v)) for k, v in value.items()]
    if hasattr(value, "items") and not isinstance(value, (str, bytes, bytearray)):
        return [(stable_value(k), stable_value(v)) for k, v in value.items()]
    if isinstance(value, list):
        return [stable_value(v) for v in value]
    if isinstance(value, tuple):
        return [stable_value(v) for v in value]
    return value


def stable_payload(module, graph_name: str):
    graph = build_graph(module, graph_name)
    nodes = list(graph.nodes())
    subset = nodes[::7]
    return {
        "graph": graph_name,
        "to_dict_of_lists": stable_value(module.to_dict_of_lists(graph)),
        "to_dict_of_lists_subset": stable_value(
            module.to_dict_of_lists(graph, nodelist=subset)
        ),
        "to_dict_of_dicts": stable_value(module.to_dict_of_dicts(graph)),
        "to_dict_of_dicts_subset_const": stable_value(
            module.to_dict_of_dicts(graph, nodelist=subset, edge_data=7)
        ),
    }


def digest_payload(payload) -> str:
    data = json.dumps(payload, sort_keys=False, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(data.encode()).hexdigest()


def proof(output: Path):
    cases = []
    for graph_name in ("MultiGraph", "MultiDiGraph"):
        fnx_payload = stable_payload(fnx, graph_name)
        nx_payload = stable_payload(nx, graph_name)
        cases.append(
            {
                "graph": graph_name,
                "matches": fnx_payload == nx_payload,
                "fnx_sha256": digest_payload(fnx_payload),
                "nx_sha256": digest_payload(nx_payload),
            }
        )
    result = {
        "cases": cases,
        "all_match": all(case["matches"] for case in cases),
        "golden_sha256": digest_payload(cases),
        "isomorphism": {
            "ordering": "node insertion order and neighbor insertion order are serialized",
            "tie_breaking": "not applicable beyond ordered graph iteration",
            "floating_point": "edge weights are copied and serialized without arithmetic",
            "rng": "none",
            "nodelist": "subset paths are included to prove fallback behavior",
        },
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, sort_keys=True))


def call_once(module, graph_name: str, operation: str):
    graph = build_graph(module, graph_name)
    if operation == "lists":
        return module.to_dict_of_lists(graph)
    if operation == "dicts":
        return module.to_dict_of_dicts(graph)
    raise ValueError(operation)


def sample(module, graph_name: str, operation: str, repeat: int):
    graph = build_graph(module, graph_name)
    func = module.to_dict_of_lists if operation == "lists" else module.to_dict_of_dicts
    timings = []
    checksum = 0
    for _ in range(repeat):
        start = time.perf_counter()
        result = func(graph)
        timings.append(time.perf_counter() - start)
        checksum += len(result)
    return {
        "mean": statistics.fmean(timings),
        "median": statistics.median(timings),
        "min": min(timings),
        "max": max(timings),
        "repeat": repeat,
        "checksum": checksum,
    }


def timing(output: Path, repeat: int):
    rows = {}
    for graph_name in ("MultiGraph", "MultiDiGraph"):
        for operation in ("lists", "dicts"):
            rows[f"fnx_{graph_name}_{operation}"] = sample(
                fnx, graph_name, operation, repeat
            )
            rows[f"nx_{graph_name}_{operation}"] = sample(nx, graph_name, operation, repeat)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(rows, indent=2, sort_keys=True) + "\n")
    print(json.dumps(rows, sort_keys=True))


def profile(output: Path, graph_name: str, operation: str, repeat: int):
    graph = build_graph(fnx, graph_name)
    func = fnx.to_dict_of_lists if operation == "lists" else fnx.to_dict_of_dicts
    profiler = cProfile.Profile()
    profiler.enable()
    for _ in range(repeat):
        func(graph)
    profiler.disable()
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w") as handle:
        stats = pstats.Stats(profiler, stream=handle).sort_stats("cumulative")
        stats.print_stats(40)


def bench_one(module_name: str, graph_name: str, operation: str, repeat: int):
    module = fnx if module_name == "fnx" else nx
    graph = build_graph(module, graph_name)
    func = module.to_dict_of_lists if operation == "lists" else module.to_dict_of_dicts
    checksum = 0
    for _ in range(repeat):
        checksum += len(func(graph))
    print(checksum)


def main():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="mode", required=True)

    proof_parser = subparsers.add_parser("proof")
    proof_parser.add_argument("--output", type=Path, required=True)

    timing_parser = subparsers.add_parser("timing")
    timing_parser.add_argument("--output", type=Path, required=True)
    timing_parser.add_argument("--repeat", type=int, default=25)

    profile_parser = subparsers.add_parser("profile")
    profile_parser.add_argument("--output", type=Path, required=True)
    profile_parser.add_argument("--graph", choices=("MultiGraph", "MultiDiGraph"), required=True)
    profile_parser.add_argument("--operation", choices=("lists", "dicts"), required=True)
    profile_parser.add_argument("--repeat", type=int, default=200)

    bench_parser = subparsers.add_parser("bench-one")
    bench_parser.add_argument("--module", choices=("fnx", "nx"), required=True)
    bench_parser.add_argument("--graph", choices=("MultiGraph", "MultiDiGraph"), required=True)
    bench_parser.add_argument("--operation", choices=("lists", "dicts"), required=True)
    bench_parser.add_argument("--repeat", type=int, default=200)

    args = parser.parse_args()
    if args.mode == "proof":
        proof(args.output)
    elif args.mode == "timing":
        timing(args.output, args.repeat)
    elif args.mode == "profile":
        profile(args.output, args.graph, args.operation, args.repeat)
    elif args.mode == "bench-one":
        bench_one(args.module, args.graph, args.operation, args.repeat)


if __name__ == "__main__":
    main()
