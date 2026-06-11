#!/usr/bin/env python3
"""Deterministic harness for br-r37-c1-7x2z3 generate_adjlist."""

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

import networkx as nx

import franken_networkx as fnx


def _payload(lines) -> str:
    return "\n".join(lines)


def _target_graphs() -> tuple[fnx.Graph, nx.Graph]:
    return fnx.barabasi_albert_graph(1800, 4, seed=101), nx.barabasi_albert_graph(
        1800, 4, seed=101
    )


def _case_graphs(name: str):
    if name == "target":
        return _target_graphs(), " "
    if name == "path_comma":
        return (fnx.path_graph(8), nx.path_graph(8)), ","
    if name == "self_loop":
        fg = fnx.Graph()
        ng = nx.Graph()
        fg.add_edges_from([(0, 0), (0, 1), (1, 2), (3, 3)])
        ng.add_edges_from([(0, 0), (0, 1), (1, 2), (3, 3)])
        return (fg, ng), " "
    if name == "strings":
        fg = fnx.Graph()
        ng = nx.Graph()
        edges = [("a", "b"), ("a", "c"), ("d", "a"), ("z", "z")]
        fg.add_edges_from(edges)
        ng.add_edges_from(edges)
        return (fg, ng), "|"
    if name == "digraph":
        fg = fnx.DiGraph()
        ng = nx.DiGraph()
        edges = [(0, 1), (1, 0), (1, 2), (3, 1)]
        fg.add_edges_from(edges)
        ng.add_edges_from(edges)
        return (fg, ng), " "
    if name == "multigraph":
        fg = fnx.MultiGraph()
        ng = nx.MultiGraph()
        fg.add_edge(0, 1, key="a")
        fg.add_edge(0, 1, key="b")
        fg.add_edge(1, 2, key="c")
        ng.add_edge(0, 1, key="a")
        ng.add_edge(0, 1, key="b")
        ng.add_edge(1, 2, key="c")
        return (fg, ng), " "
    raise ValueError(f"unknown case {name!r}")


def _generate(backend: str, graph, delimiter: str) -> str:
    if backend == "fnx":
        return _payload(fnx.generate_adjlist(graph, delimiter=delimiter))
    if backend == "nx":
        return _payload(nx.generate_adjlist(graph, delimiter=delimiter))
    raise ValueError(f"unknown backend {backend!r}")


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _json_with_self_hash(payload: dict) -> dict:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    payload = dict(payload)
    payload["self_sha256_sort_keys_compact"] = hashlib.sha256(encoded).hexdigest()
    return payload


def run_golden(backend: str) -> dict:
    cases = {}
    for name in ("target", "path_comma", "self_loop", "strings", "digraph", "multigraph"):
        (fg, ng), delimiter = _case_graphs(name)
        text = _generate(backend, fg if backend == "fnx" else ng, delimiter)
        cases[name] = {
            "delimiter": delimiter,
            "text_sha256": _digest(text),
            "line_count": len(text.splitlines()),
            "prefix": text[:240],
        }
    return _json_with_self_hash(
        {
            "bead": "br-r37-c1-7x2z3",
            "backend": backend,
            "algorithm": "generate_adjlist",
            "cases": cases,
        }
    )


def run_proof() -> dict:
    cases = {}
    for name in ("target", "path_comma", "self_loop", "strings", "digraph", "multigraph"):
        (fg, ng), delimiter = _case_graphs(name)
        fnx_text = _generate("fnx", fg, delimiter)
        nx_text = _generate("nx", ng, delimiter)
        cases[name] = {
            "delimiter": delimiter,
            "fnx_sha256": _digest(fnx_text),
            "nx_sha256": _digest(nx_text),
            "exact_equal": fnx_text == nx_text,
            "line_count": len(fnx_text.splitlines()),
            "prefix": fnx_text[:240],
        }
    return _json_with_self_hash(
        {
            "bead": "br-r37-c1-7x2z3",
            "algorithm": "generate_adjlist",
            "cases": cases,
            "all_exact_equal": all(case["exact_equal"] for case in cases.values()),
        }
    )


def run_bench(backend: str, repeats: int, warmups: int) -> dict:
    fg, ng = _target_graphs()
    graph = fg if backend == "fnx" else ng
    for _ in range(warmups):
        _generate(backend, graph, " ")
    samples = []
    last = ""
    for _ in range(repeats):
        start = time.perf_counter()
        last = _generate(backend, graph, " ")
        samples.append((time.perf_counter() - start) * 1000.0)
    return {
        "bead": "br-r37-c1-7x2z3",
        "backend": backend,
        "graph": "barabasi_albert_graph(1800, 4, seed=101)",
        "repeats": repeats,
        "warmups": warmups,
        "count": len(samples),
        "min_ms": min(samples),
        "p50_ms": statistics.median(samples),
        "mean_ms": statistics.fmean(samples),
        "p95_ms": sorted(samples)[int(0.95 * (len(samples) - 1))],
        "max_ms": max(samples),
        "text_sha256": _digest(last),
        "line_count": len(last.splitlines()),
    }


def run_profile(backend: str, repeats: int, output: Path) -> None:
    fg, ng = _target_graphs()
    graph = fg if backend == "fnx" else ng

    def _work() -> None:
        for _ in range(repeats):
            _generate(backend, graph, " ")

    profile = cProfile.Profile()
    profile.enable()
    _work()
    profile.disable()
    with output.open("w", encoding="utf-8") as handle:
        pstats.Stats(profile, stream=handle).strip_dirs().sort_stats("cumtime").print_stats(40)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("golden", "proof", "bench", "profile"), required=True)
    parser.add_argument("--backend", choices=("fnx", "nx"), default="fnx")
    parser.add_argument("--output")
    parser.add_argument("--repeats", type=int, default=100)
    parser.add_argument("--warmups", type=int, default=10)
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    if args.mode == "golden":
        payload = run_golden(args.backend)
    elif args.mode == "proof":
        payload = run_proof()
    elif args.mode == "bench":
        payload = run_bench(args.backend, args.repeats, args.warmups)
    else:
        if args.output is None:
            parser.error("--output is required for profile mode")
        run_profile(args.backend, args.repeats, Path(args.output))
        return 0

    encoded = json.dumps(payload, indent=2, sort_keys=True)
    if args.output:
        Path(args.output).write_text(encoded + "\n", encoding="utf-8")
    if not args.quiet:
        print(encoded)
    return 0


if __name__ == "__main__":
    sys.exit(main())
