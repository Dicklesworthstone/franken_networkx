#!/usr/bin/env python3
"""Benchmark and proof harness for streaming list(DiGraph.in_edges())."""

from __future__ import annotations

import argparse
import cProfile
import hashlib
import json
import pstats
import subprocess
import sys
import time
from pathlib import Path

import networkx as nx

import franken_networkx as fnx


N = 1800
P = 0.006
SEED = 15


def repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def head_metadata() -> dict[str, object]:
    root = repo_root()
    try:
        head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
        short = subprocess.check_output(
            ["git", "log", "-1", "--oneline"],
            cwd=root,
            text=True,
        ).strip()
    except Exception:
        head = "unknown"
        short = "unknown"
    return {
        "head": head,
        "head_short": short,
        "repo_root": str(root),
        "python": sys.version,
        "franken_networkx_file": fnx.__file__,
        "networkx_file": nx.__file__,
        "networkx_version": nx.__version__,
        "graph": {
            "family": "DiGraph(gnp_random_graph(n, p, seed, directed=True))",
            "n": N,
            "p": P,
            "seed": SEED,
        },
        "workload": "list(DiGraph.in_edges())",
    }


def build_nx_graph() -> nx.DiGraph:
    return nx.gnp_random_graph(N, P, seed=SEED, directed=True)


def build_fnx_graph(source: nx.DiGraph) -> fnx.DiGraph:
    graph = fnx.DiGraph()
    graph.add_nodes_from(source.nodes())
    graph.add_edges_from(source.edges())
    return graph


def payload(edges: list[tuple[object, object]]) -> bytes:
    return json.dumps(edges, separators=(",", ":"), sort_keys=False).encode()


def digest_edges(edges: list[tuple[object, object]]) -> str:
    return hashlib.sha256(payload(edges)).hexdigest()


def mutation_error(module: object, mutation: str) -> dict[str, object]:
    graph = module.DiGraph()
    graph.add_edges_from([(0, 1), (1, 2), (2, 3)])
    iterator = iter(graph.in_edges)
    first = next(iterator)
    if mutation == "edge":
        graph.add_edge(3, 4)
    elif mutation == "node":
        graph.add_node(9)
    else:
        raise ValueError(mutation)
    try:
        next(iterator)
    except Exception as exc:
        return {
            "first": first,
            "type": type(exc).__name__,
            "message": str(exc),
        }
    return {
        "first": first,
        "type": None,
        "message": None,
    }


def graphs() -> tuple[nx.DiGraph, fnx.DiGraph]:
    nx_graph = build_nx_graph()
    return nx_graph, build_fnx_graph(nx_graph)


def bench(mode: str, loops: int) -> dict[str, object]:
    nx_graph, fnx_graph = graphs()
    graph = fnx_graph if mode == "fnx" else nx_graph
    total_edges = 0
    digest = ""
    start = time.perf_counter()
    for _ in range(loops):
        edges = list(graph.in_edges())
        total_edges += len(edges)
        digest = digest_edges(edges)
    elapsed = time.perf_counter() - start
    return {
        "mode": mode,
        "loops": loops,
        "elapsed_seconds": elapsed,
        "seconds_per_loop": elapsed / loops,
        "edges_per_loop": graph.number_of_edges(),
        "total_edges": total_edges,
        "digest": digest,
        "metadata": head_metadata(),
    }


def golden() -> dict[str, object]:
    nx_graph, fnx_graph = graphs()
    nx_edges = list(nx_graph.in_edges())
    fnx_edges = list(fnx_graph.in_edges())
    nx_sha = digest_edges(nx_edges)
    fnx_sha = digest_edges(fnx_edges)
    mutation_cases = {}
    for mutation in ("edge", "node"):
        nx_error = mutation_error(nx, mutation)
        fnx_error = mutation_error(fnx, mutation)
        mutation_cases[mutation] = {
            "match": nx_error == fnx_error,
            "nx": nx_error,
            "fnx": fnx_error,
        }
    return {
        "match": nx_edges == fnx_edges,
        "nx_sha256": nx_sha,
        "fnx_sha256": fnx_sha,
        "edge_count": len(nx_edges),
        "mutation_cases": mutation_cases,
        "samples": {
            "first_8": nx_edges[:8],
            "last_8": nx_edges[-8:],
        },
        "metadata": head_metadata(),
    }


def profiled(loops: int, output: str | None) -> None:
    _nx_graph, fnx_graph = graphs()

    def target() -> None:
        for _ in range(loops):
            list(fnx_graph.in_edges())

    profiler = cProfile.Profile()
    profiler.enable()
    target()
    profiler.disable()
    stats = pstats.Stats(profiler)
    stats.sort_stats("cumulative")
    if output:
        stats.dump_stats(output)
    stats.print_stats(40)


def write_or_print(data: dict[str, object], output: str | None) -> None:
    rendered = json.dumps(data, indent=2, sort_keys=True)
    if output:
        Path(output).write_text(rendered + "\n", encoding="utf-8")
    print(rendered)


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    for name in ("bench-fnx", "bench-nx"):
        p = sub.add_parser(name)
        p.add_argument("--loops", type=int, default=200)
        p.add_argument("--output")
    p = sub.add_parser("golden")
    p.add_argument("--output")
    p = sub.add_parser("profile-fnx")
    p.add_argument("--loops", type=int, default=200)
    p.add_argument("--output")
    args = parser.parse_args()

    if args.cmd == "bench-fnx":
        write_or_print(bench("fnx", args.loops), args.output)
    elif args.cmd == "bench-nx":
        write_or_print(bench("nx", args.loops), args.output)
    elif args.cmd == "golden":
        write_or_print(golden(), args.output)
    elif args.cmd == "profile-fnx":
        profiled(args.loops, args.output)


if __name__ == "__main__":
    main()
