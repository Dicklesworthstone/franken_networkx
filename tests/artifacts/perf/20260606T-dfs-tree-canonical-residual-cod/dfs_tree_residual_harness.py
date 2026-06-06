#!/usr/bin/env python3
"""Baseline/profile/proof harness for br-r37-c1-wvbzw dfs_tree residual."""

from __future__ import annotations

import argparse
import cProfile
import hashlib
import io
import json
import pstats
import statistics
import time
from pathlib import Path
from typing import Callable, Iterable

import franken_networkx as fnx
import networkx as nx


ARTIFACT_DIR = Path(__file__).resolve().parent
NODES = 400
EDGES = 2000
SEEDS = (20260606, 20260607, 20260608)
SOURCE = 0


def _build_graphs(directed: bool, seed: int):
    seed_graph = nx.gnm_random_graph(NODES, EDGES, seed=seed, directed=directed)
    edges = list(seed_graph.edges())
    nx_graph = nx.DiGraph() if directed else nx.Graph()
    fnx_graph = fnx.DiGraph() if directed else fnx.Graph()
    nx_graph.add_nodes_from(seed_graph.nodes())
    fnx_graph.add_nodes_from(seed_graph.nodes())
    nx_graph.add_edges_from(edges)
    fnx_graph.add_edges_from(edges)
    return fnx_graph, nx_graph, edges


def _edges(tree) -> list[tuple[int, int]]:
    return [(int(u), int(v)) for u, v in tree.edges()]


def _nodes(tree) -> list[int]:
    return [int(n) for n in tree.nodes()]


def _time_call(fn: Callable[[], object], repeats: int) -> list[int]:
    samples: list[int] = []
    for _ in range(repeats):
        start = time.perf_counter_ns()
        fn()
        samples.append(time.perf_counter_ns() - start)
    return samples


def _summary(samples_ns: Iterable[int]) -> dict[str, float]:
    samples = sorted(samples_ns)
    return {
        "min_ms": samples[0] / 1_000_000.0,
        "median_ms": statistics.median(samples) / 1_000_000.0,
        "p95_ms": samples[int((len(samples) - 1) * 0.95)] / 1_000_000.0,
        "p99_ms": samples[int((len(samples) - 1) * 0.99)] / 1_000_000.0,
        "max_ms": samples[-1] / 1_000_000.0,
    }


def benchmark(args: argparse.Namespace) -> None:
    fnx_graph, nx_graph, edges = _build_graphs(True, SEEDS[0])
    for _ in range(args.warmup):
        fnx.dfs_tree(fnx_graph, SOURCE)
        nx.dfs_tree(nx_graph, SOURCE)

    fnx_samples = _time_call(lambda: fnx.dfs_tree(fnx_graph, SOURCE), args.runs)
    nx_samples = _time_call(lambda: nx.dfs_tree(nx_graph, SOURCE), args.runs)
    fnx_summary = _summary(fnx_samples)
    nx_summary = _summary(nx_samples)
    result = {
        "benchmark": "dfs_tree_residual",
        "graph": {
            "directed": True,
            "nodes": NODES,
            "edges": len(edges),
            "seed": SEEDS[0],
            "source": SOURCE,
            "fixture": "networkx.gnm_random_graph(n=400, m=2000, directed=True)",
        },
        "runs": args.runs,
        "warmup": args.warmup,
        "fnx_dfs_tree": fnx_summary,
        "networkx_dfs_tree": nx_summary,
        "ratio_fnx_over_networkx_min": fnx_summary["min_ms"] / nx_summary["min_ms"],
        "ratio_fnx_over_networkx_median": fnx_summary["median_ms"] / nx_summary["median_ms"],
    }
    (ARTIFACT_DIR / "baseline_min_of_n.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, indent=2, sort_keys=True))


def profile(args: argparse.Namespace) -> None:
    fnx_graph, nx_graph, edges = _build_graphs(True, SEEDS[0])
    for _ in range(args.warmup):
        fnx.dfs_tree(fnx_graph, SOURCE)
        nx.dfs_tree(nx_graph, SOURCE)

    profiler = cProfile.Profile()
    profiler.enable()
    for _ in range(args.calls):
        fnx.dfs_tree(fnx_graph, SOURCE)
    profiler.disable()

    stream = io.StringIO()
    pstats.Stats(profiler, stream=stream).strip_dirs().sort_stats("tottime").print_stats(args.top)
    text = stream.getvalue()
    payload = {
        "profile": "fnx.dfs_tree",
        "graph": {
            "directed": True,
            "nodes": NODES,
            "edges": len(edges),
            "seed": SEEDS[0],
            "source": SOURCE,
        },
        "calls": args.calls,
        "warmup": args.warmup,
        "sort": "tottime",
        "top": args.top,
        "cprofile_text": text,
    }
    (ARTIFACT_DIR / "cprofile_fnx_dfs_tree.txt").write_text(text, encoding="utf-8")
    (ARTIFACT_DIR / "cprofile_fnx_dfs_tree.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(text, end="")


def proof(_: argparse.Namespace) -> None:
    cases = []
    mismatch_count = 0
    for directed in (True, False):
        for seed in SEEDS:
            fnx_graph, nx_graph, input_edges = _build_graphs(directed, seed)
            fnx_tree = fnx.dfs_tree(fnx_graph, SOURCE)
            nx_tree = nx.dfs_tree(nx_graph, SOURCE)
            fnx_nodes = _nodes(fnx_tree)
            nx_nodes = _nodes(nx_tree)
            fnx_edges = _edges(fnx_tree)
            nx_edges = _edges(nx_tree)
            nodes_match = fnx_nodes == nx_nodes
            edges_match = fnx_edges == nx_edges
            iso_graph = nx.DiGraph()
            iso_graph.add_nodes_from(fnx_nodes)
            iso_graph.add_edges_from(fnx_edges)
            isomorphic = nx.is_isomorphic(iso_graph, nx_tree)
            if not (nodes_match and edges_match and isomorphic):
                mismatch_count += 1
            cases.append(
                {
                    "directed": directed,
                    "seed": seed,
                    "input_nodes": NODES,
                    "input_edges": len(input_edges),
                    "source": SOURCE,
                    "fnx_tree_nodes": len(fnx_nodes),
                    "nx_tree_nodes": len(nx_nodes),
                    "fnx_tree_edges": len(fnx_edges),
                    "nx_tree_edges": len(nx_edges),
                    "nodes_match_order": nodes_match,
                    "edges_match_order": edges_match,
                    "isomorphic": isomorphic,
                    "fnx_nodes": fnx_nodes,
                    "nx_nodes": nx_nodes,
                    "fnx_edges": fnx_edges,
                    "nx_edges": nx_edges,
                }
            )

    canonical = json.dumps(cases, sort_keys=True, separators=(",", ":")).encode("utf-8")
    digest = hashlib.sha256(canonical).hexdigest()
    result = {
        "proof": "dfs_tree_ordering_isomorphism",
        "cases": cases,
        "case_count": len(cases),
        "mismatch_count": mismatch_count,
        "sha256": digest,
        "ordering_preserved": mismatch_count == 0,
        "tie_breaking": "same input node and edge insertion order, no sort_neighbors",
        "floating_point": "N/A",
        "rng_seeds": list(SEEDS),
    }
    (ARTIFACT_DIR / "golden_ordering_isomorphism.canonical.json").write_bytes(canonical)
    (ARTIFACT_DIR / "golden_ordering_isomorphism.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (ARTIFACT_DIR / "golden_ordering_isomorphism.sha256").write_text(
        f"{digest}  golden_ordering_isomorphism.canonical.json\n",
        encoding="utf-8",
    )
    print(json.dumps({k: v for k, v in result.items() if k != "cases"}, indent=2, sort_keys=True))


def main() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    bench_parser = subparsers.add_parser("benchmark")
    bench_parser.add_argument("--runs", type=int, default=1000)
    bench_parser.add_argument("--warmup", type=int, default=100)
    bench_parser.set_defaults(func=benchmark)

    profile_parser = subparsers.add_parser("profile")
    profile_parser.add_argument("--calls", type=int, default=1000)
    profile_parser.add_argument("--warmup", type=int, default=100)
    profile_parser.add_argument("--top", type=int, default=20)
    profile_parser.set_defaults(func=profile)

    proof_parser = subparsers.add_parser("proof")
    proof_parser.set_defaults(func=proof)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
