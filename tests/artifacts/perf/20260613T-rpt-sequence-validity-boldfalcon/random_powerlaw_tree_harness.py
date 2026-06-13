#!/usr/bin/env python3
"""Focused random_powerlaw_tree benchmark and golden-output harness."""

from __future__ import annotations

import argparse
import cProfile
import hashlib
import importlib.util
import json
from pathlib import Path
import pstats
import statistics
import sys
import time


CASE = {
    "n": 300,
    "gamma": 3,
    "seed": 5,
    "tries": 1000,
}


def load_fnx(repo_root: Path, extension: Path):
    package_dir = repo_root / "python"
    sys.path.insert(0, str(package_dir))
    spec = importlib.util.spec_from_file_location("franken_networkx._fnx", extension)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load extension from {extension}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["franken_networkx._fnx"] = module
    spec.loader.exec_module(module)
    import franken_networkx as fnx

    return fnx


def graph_payload(graph):
    return {
        "directed": graph.is_directed(),
        "multigraph": graph.is_multigraph(),
        "graph": sorted((str(k), repr(v)) for k, v in graph.graph.items()),
        "nodes": [
            [repr(node), sorted((str(k), repr(v)) for k, v in data.items())]
            for node, data in graph.nodes(data=True)
        ],
        "edges": [
            [repr(u), repr(v), sorted((str(k), repr(vv)) for k, vv in data.items())]
            for u, v, data in graph.edges(data=True)
        ],
    }


def digest_payload(payload) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def make_graph(impl, args):
    if impl == "fnx":
        fnx = load_fnx(args.repo_root, args.extension)
        return fnx.random_powerlaw_tree(**CASE)
    import networkx as nx

    return nx.random_powerlaw_tree(**CASE)


def make_factory(impl, args):
    if impl == "fnx":
        fnx = load_fnx(args.repo_root, args.extension)
        return lambda: fnx.random_powerlaw_tree(**CASE)
    import networkx as nx

    return lambda: nx.random_powerlaw_tree(**CASE)


def command_golden(args):
    fnx = load_fnx(args.repo_root, args.extension)
    import networkx as nx

    fnx_graph = fnx.random_powerlaw_tree(**CASE)
    nx_graph = nx.random_powerlaw_tree(**CASE)
    fnx_payload = graph_payload(fnx_graph)
    nx_payload = graph_payload(nx_graph)
    result = {
        "case": CASE,
        "fnx_sha256": digest_payload(fnx_payload),
        "nx_sha256": digest_payload(nx_payload),
        "match": fnx_payload == nx_payload,
        "node_count": fnx_graph.number_of_nodes(),
        "edge_count": fnx_graph.number_of_edges(),
        "fnx_first_edges": fnx_payload["edges"][:12],
        "nx_first_edges": nx_payload["edges"][:12],
        "fnx_last_edges": fnx_payload["edges"][-12:],
        "nx_last_edges": nx_payload["edges"][-12:],
    }
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0 if result["match"] else 1


def command_bench(args):
    factory = make_factory(args.impl, args)
    samples = []
    for _ in range(args.warmups):
        factory()
    for _ in range(args.loops):
        start = time.perf_counter()
        graph = factory()
        elapsed = time.perf_counter() - start
        samples.append(elapsed)
        if graph.number_of_edges() != CASE["n"] - 1:
            raise AssertionError("tree edge count changed")
    result = {
        "case": CASE,
        "impl": args.impl,
        "loops": args.loops,
        "warmups": args.warmups,
        "median_seconds": statistics.median(samples),
        "mean_seconds": statistics.fmean(samples),
        "min_seconds": min(samples),
        "max_seconds": max(samples),
        "samples_seconds": samples,
    }
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0


def command_profile(args):
    factory = make_factory(args.impl, args)
    profile = cProfile.Profile()
    profile.enable()
    for _ in range(args.loops):
        factory()
    profile.disable()
    stats = pstats.Stats(profile).sort_stats("cumulative")
    stats.print_stats(args.limit)
    return 0


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--extension", type=Path, required=True)
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("golden")

    bench = subparsers.add_parser("bench")
    bench.add_argument("--impl", choices=("fnx", "nx"), required=True)
    bench.add_argument("--loops", type=int, default=31)
    bench.add_argument("--warmups", type=int, default=5)

    profile = subparsers.add_parser("profile")
    profile.add_argument("--impl", choices=("fnx", "nx"), required=True)
    profile.add_argument("--loops", type=int, default=1)
    profile.add_argument("--limit", type=int, default=40)

    return parser.parse_args()


def main():
    args = parse_args()
    if args.command == "golden":
        return command_golden(args)
    if args.command == "bench":
        return command_bench(args)
    if args.command == "profile":
        return command_profile(args)
    raise AssertionError(args.command)


if __name__ == "__main__":
    raise SystemExit(main())
