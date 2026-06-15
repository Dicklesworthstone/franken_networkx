#!/usr/bin/env python3
"""Baseline/proof harness for reverse(copy=False).edges materialization."""

from __future__ import annotations

import argparse
import cProfile
import hashlib
import json
import pstats
import statistics
import sys
import time
from pathlib import Path
from typing import Any

import franken_networkx as fnx
import networkx as nx


DEFAULT_EXPECTED_SHA = (
    "6c02e12d4919dc3896f61bb46132765c58d07395023846106aad288d1c918feb"
)


def _json_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def _sha(value: Any) -> str:
    return hashlib.sha256(_json_bytes(value)).hexdigest()


def _base_edges(args: argparse.Namespace) -> list[tuple[int, int]]:
    base = nx.watts_strogatz_graph(args.nodes, args.k, args.p, seed=args.seed)
    return list(base.edges())


def build_graph(impl: str, args: argparse.Namespace) -> Any:
    module = fnx if impl == "fnx" else nx
    graph = module.DiGraph()
    graph.add_nodes_from(range(args.nodes))
    base_edges = _base_edges(args)
    if args.style == "oriented":
        graph.add_edges_from(base_edges)
    elif args.style == "bidirected":
        graph.add_edges_from(base_edges)
        graph.add_edges_from((v, u) for u, v in base_edges)
    elif args.style == "digraph_ctor":
        undirected = module.Graph()
        undirected.add_nodes_from(range(args.nodes))
        undirected.add_edges_from(base_edges)
        graph = module.DiGraph(undirected)
    else:
        raise ValueError(args.style)
    return graph


def materialize_edges(impl: str, args: argparse.Namespace) -> list[tuple[Any, ...]]:
    graph = build_graph(impl, args)
    return list(graph.reverse(copy=False).edges())


def materialize_from_graph(graph: Any) -> list[tuple[Any, ...]]:
    return list(graph.reverse(copy=False).edges())


def proof_payload(args: argparse.Namespace) -> dict[str, Any]:
    fnx_edges = materialize_edges("fnx", args)
    nx_edges = materialize_edges("nx", args)
    fnx_sha = _sha(fnx_edges)
    nx_sha = _sha(nx_edges)
    return {
        "case": {
            "nodes": args.nodes,
            "k": args.k,
            "p": args.p,
            "seed": args.seed,
            "style": args.style,
            "operation": "list(DG.reverse(copy=False).edges())",
        },
        "environment": {
            "python": sys.version,
            "fnx_package": getattr(fnx, "__file__", None),
            "networkx_version": getattr(nx, "__version__", None),
        },
        "digest_recipe": "sha256(json.dumps(edges, sort_keys=True, separators=(',', ':')).encode())",
        "expected_sha": args.expected_sha,
        "fnx_sha": fnx_sha,
        "nx_sha": nx_sha,
        "fnx_matches_nx": fnx_edges == nx_edges,
        "fnx_matches_expected": fnx_sha == args.expected_sha,
        "nx_matches_expected": nx_sha == args.expected_sha,
        "edge_count": len(fnx_edges),
        "first_edges": [list(edge) for edge in fnx_edges[:12]],
        "last_edges": [list(edge) for edge in fnx_edges[-12:]],
    }


def command_golden(args: argparse.Namespace) -> int:
    payload = proof_payload(args)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return 0 if payload["fnx_matches_nx"] else 1


def command_bench(args: argparse.Namespace) -> int:
    samples: list[float] = []
    marker = None
    graph = build_graph(args.impl, args)
    for _ in range(args.repeats):
        start = time.perf_counter()
        edges = materialize_from_graph(graph)
        elapsed = time.perf_counter() - start
        marker = [len(edges), _sha(edges)]
        samples.append(elapsed)
    payload = {
        "impl": args.impl,
        "repeats": args.repeats,
        "samples_s": samples,
        "min_s": min(samples),
        "median_s": statistics.median(samples),
        "mean_s": statistics.fmean(samples),
        "max_s": max(samples),
        "marker": marker,
        "case": {
            "nodes": args.nodes,
            "k": args.k,
            "p": args.p,
            "seed": args.seed,
            "style": args.style,
        },
    }
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return 0


def command_once(args: argparse.Namespace) -> int:
    graph = build_graph(args.impl, args)
    edges = None
    for _ in range(args.loops):
        edges = materialize_from_graph(graph)
    assert edges is not None
    print(json.dumps({"impl": args.impl, "edge_count": len(edges), "sha": _sha(edges)}))
    return 0


def command_profile(args: argparse.Namespace) -> int:
    graph = build_graph(args.impl, args)
    profiler = cProfile.Profile()
    edges = None
    profiler.enable()
    for _ in range(args.loops):
        edges = materialize_from_graph(graph)
    profiler.disable()
    assert edges is not None
    marker = [len(edges), _sha(edges)]
    with args.output.open("w", encoding="utf-8") as handle:
        handle.write(json.dumps({"impl": args.impl, "loops": args.loops, "marker": marker}) + "\n")
        pstats.Stats(profiler, stream=handle).strip_dirs().sort_stats("cumtime").print_stats(args.limit)
    return 0


def add_case_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--nodes", type=int, default=1200)
    parser.add_argument("--k", type=int, default=10)
    parser.add_argument("--p", type=float, default=0.2)
    parser.add_argument("--seed", type=int, default=5)
    parser.add_argument(
        "--style",
        choices=("digraph_ctor", "bidirected", "oriented"),
        default="digraph_ctor",
    )
    parser.add_argument("--expected-sha", default=DEFAULT_EXPECTED_SHA)


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    golden = sub.add_parser("golden")
    add_case_args(golden)
    golden.add_argument("--output", type=Path, required=True)
    golden.set_defaults(func=command_golden)

    bench = sub.add_parser("bench")
    add_case_args(bench)
    bench.add_argument("--impl", choices=("fnx", "nx"), required=True)
    bench.add_argument("--repeats", type=int, default=21)
    bench.add_argument("--output", type=Path, required=True)
    bench.set_defaults(func=command_bench)

    once = sub.add_parser("once")
    add_case_args(once)
    once.add_argument("--impl", choices=("fnx", "nx"), required=True)
    once.add_argument("--loops", type=int, default=100)
    once.set_defaults(func=command_once)

    profile = sub.add_parser("profile")
    add_case_args(profile)
    profile.add_argument("--impl", choices=("fnx", "nx"), default="fnx")
    profile.add_argument("--loops", type=int, default=50)
    profile.add_argument("--limit", type=int, default=35)
    profile.add_argument("--output", type=Path, required=True)
    profile.set_defaults(func=command_profile)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
