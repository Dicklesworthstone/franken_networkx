#!/usr/bin/env python3
"""Benchmark/proof harness for br-r37-c1-04z53.61 block-graph k_components."""

from __future__ import annotations

import argparse
import cProfile
import hashlib
import json
import pstats
import tempfile
import time
from pathlib import Path

import franken_networkx as fnx
import networkx as nx


def _nx_k_components(graph):
    return getattr(nx.k_components, "orig_func", nx.k_components)(graph)


def _canonical(result):
    return [
        {
            "k": k,
            "components": [sorted(repr(node) for node in component) for component in value],
            "value_type": type(value).__name__,
            "component_types": [type(component).__name__ for component in value],
        }
        for k, value in result.items()
    ]


def _graph(library, edges):
    graph = library.Graph()
    graph.add_edges_from(edges)
    return graph


def _cases():
    return [
        ("barbell4_1", fnx.barbell_graph(4, 1), nx.barbell_graph(4, 1)),
        ("barbell5_2", fnx.barbell_graph(5, 2), nx.barbell_graph(5, 2)),
        (
            "bowtie",
            _graph(fnx, [(0, 1), (1, 2), (2, 0), (2, 3), (3, 4), (4, 2)]),
            _graph(nx, [(0, 1), (1, 2), (2, 0), (2, 3), (3, 4), (4, 2)]),
        ),
        (
            "k4_tri",
            _graph(
                fnx,
                [(0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3), (3, 4), (4, 5), (5, 3)],
            ),
            _graph(
                nx,
                [(0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3), (3, 4), (4, 5), (5, 3)],
            ),
        ),
        (
            "nonblock_square_diagonal_delegate",
            _graph(fnx, [(0, 1), (1, 2), (2, 3), (3, 0), (0, 2)]),
            _graph(nx, [(0, 1), (1, 2), (2, 3), (3, 0), (0, 2)]),
        ),
    ]


def proof(out: Path) -> None:
    rows = []
    for name, f_graph, nx_graph in _cases():
        f_result = fnx.k_components(f_graph)
        nx_result = _nx_k_components(nx_graph)
        rows.append(
            {
                "case": name,
                "fnx": _canonical(f_result),
                "nx": _canonical(nx_result),
                "match": _canonical(f_result) == _canonical(nx_result),
                "key_order": list(f_result.keys()),
            }
        )
    payload = {
        "fnx_module": "franken_networkx",
        "nx_version": nx.__version__,
        "cases": rows,
        "all_match": all(row["match"] for row in rows),
        "isomorphism": {
            "ordering_preserved": "clique blocks use native biconnected-component order; k descends from max clique size - 1",
            "tie_breaking_unchanged": "block-graph clique blocks have closed-form k-components",
            "floating_point": "N/A",
            "rng": "N/A",
        },
    }
    text = json.dumps(payload, sort_keys=True, indent=2)
    out.write_text(text + "\n", encoding="utf-8")
    print(hashlib.sha256((text + "\n").encode("utf-8")).hexdigest())
    if not payload["all_match"]:
        raise SystemExit("proof mismatch")


def time_barbell(n: int, repeats: int, which: str) -> None:
    if which == "fnx":
        graph = fnx.barbell_graph(n, 1)
        func = fnx.k_components
    elif which == "nx":
        graph = nx.barbell_graph(n, 1)
        func = _nx_k_components
    else:
        raise ValueError(which)

    result = None
    start = time.perf_counter()
    for _ in range(repeats):
        result = func(graph)
    elapsed = time.perf_counter() - start
    payload = {
        "which": which,
        "n": n,
        "repeats": repeats,
        "seconds": elapsed,
        "seconds_per_call": elapsed / repeats,
        "result_sha256": hashlib.sha256(
            json.dumps(_canonical(result), sort_keys=True).encode("utf-8")
        ).hexdigest(),
    }
    print(json.dumps(payload, sort_keys=True))


def profile_barbell(n: int, repeats: int, out: Path) -> None:
    graph = fnx.barbell_graph(n, 1)
    profiler = cProfile.Profile()
    profiler.enable()
    for _ in range(repeats):
        fnx.k_components(graph)
    profiler.disable()
    with tempfile.NamedTemporaryFile() as tmp:
        profiler.dump_stats(tmp.name)
        stats = pstats.Stats(tmp.name)
        stats.sort_stats("cumulative")
        with out.open("w", encoding="utf-8") as handle:
            stats.stream = handle
            stats.print_stats(40)


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    proof_parser = sub.add_parser("proof")
    proof_parser.add_argument("--out", type=Path, required=True)
    time_parser = sub.add_parser("time")
    time_parser.add_argument("--n", type=int, default=100)
    time_parser.add_argument("--repeats", type=int, default=5)
    time_parser.add_argument("--which", choices=["fnx", "nx"], default="fnx")
    profile_parser = sub.add_parser("profile")
    profile_parser.add_argument("--n", type=int, default=100)
    profile_parser.add_argument("--repeats", type=int, default=1)
    profile_parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    if args.cmd == "proof":
        proof(args.out)
    elif args.cmd == "time":
        time_barbell(args.n, args.repeats, args.which)
    else:
        profile_barbell(args.n, args.repeats, args.out)


if __name__ == "__main__":
    main()
