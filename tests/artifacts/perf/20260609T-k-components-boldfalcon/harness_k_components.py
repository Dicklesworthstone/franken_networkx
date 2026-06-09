#!/usr/bin/env python3
"""Benchmark and proof harness for br-r37-c1-lnrxj k_components."""

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


def _nx_k_components(graph, flow_func=None):
    func = getattr(nx.k_components, "orig_func", nx.k_components)
    return func(graph, flow_func=flow_func)


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


def _cases():
    self_loop_density = fnx.Graph()
    self_loop_density.add_nodes_from([0, 1, 2])
    self_loop_density.add_edges_from([(0, 1), (1, 2), (0, 0)])

    nx_self_loop_density = nx.Graph()
    nx_self_loop_density.add_nodes_from([0, 1, 2])
    nx_self_loop_density.add_edges_from([(0, 1), (1, 2), (0, 0)])

    left_right = fnx.Graph()
    left_right.add_edges_from(
        [(0, 1), (1, 2), (2, 0), (2, 3), (3, 4), (4, 5), (5, 3)]
    )
    nx_left_right = nx.Graph()
    nx_left_right.add_edges_from(
        [(0, 1), (1, 2), (2, 0), (2, 3), (3, 4), (4, 5), (5, 3)]
    )

    return [
        ("complete0", fnx.complete_graph(0), nx.complete_graph(0)),
        ("complete1", fnx.complete_graph(1), nx.complete_graph(1)),
        ("complete2", fnx.complete_graph(2), nx.complete_graph(2)),
        ("complete5", fnx.complete_graph(5), nx.complete_graph(5)),
        ("complete75", fnx.complete_graph(75), nx.complete_graph(75)),
        ("path5", fnx.path_graph(5), nx.path_graph(5)),
        ("two_triangles_bridge", left_right, nx_left_right),
        ("selfloop_density1", self_loop_density, nx_self_loop_density),
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
        "fnx_file": fnx.__file__,
        "nx_version": nx.__version__,
        "cases": rows,
        "all_match": all(row["match"] for row in rows),
        "isomorphism": {
            "ordering_preserved": "dict keys descend from n-1 to 1 for complete graphs; non-complete cases delegate",
            "tie_breaking_unchanged": "complete graph has one component at each level; no ambiguous tie",
            "floating_point": "N/A",
            "rng": "N/A",
        },
    }
    text = json.dumps(payload, sort_keys=True, indent=2)
    out.write_text(text + "\n", encoding="utf-8")
    print(hashlib.sha256((text + "\n").encode("utf-8")).hexdigest())
    if not payload["all_match"]:
        raise SystemExit("proof mismatch")


def time_complete(n: int, repeats: int, which: str) -> None:
    if which == "fnx":
        graph = fnx.complete_graph(n)
        func = fnx.k_components
    elif which == "nx":
        graph = nx.complete_graph(n)
        func = _nx_k_components
    else:
        raise ValueError(which)

    start = time.perf_counter()
    result = None
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


def profile_complete(n: int, repeats: int, out: Path) -> None:
    graph = fnx.complete_graph(n)
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
    time_parser.add_argument("--n", type=int, default=300)
    time_parser.add_argument("--repeats", type=int, default=3)
    time_parser.add_argument("--which", choices=["fnx", "nx"], default="fnx")

    profile_parser = sub.add_parser("profile")
    profile_parser.add_argument("--n", type=int, default=250)
    profile_parser.add_argument("--repeats", type=int, default=1)
    profile_parser.add_argument("--out", type=Path, required=True)

    args = parser.parse_args()
    if args.cmd == "proof":
        proof(args.out)
    elif args.cmd == "time":
        time_complete(args.n, args.repeats, args.which)
    else:
        profile_complete(args.n, args.repeats, args.out)


if __name__ == "__main__":
    main()
