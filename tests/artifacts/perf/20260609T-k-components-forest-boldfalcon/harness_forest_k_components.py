#!/usr/bin/env python3
"""Benchmark/proof harness for br-r37-c1-1m567 forest k_components pass."""

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


def _cases():
    triangle_tail = fnx.Graph()
    nx_triangle_tail = nx.Graph()
    for graph in (triangle_tail, nx_triangle_tail):
        graph.add_edges_from([(0, 1), (1, 2), (2, 0), (2, 3)])

    self_loop = fnx.Graph()
    nx_self_loop = nx.Graph()
    for graph in (self_loop, nx_self_loop):
        graph.add_nodes_from([0, 1, 2])
        graph.add_edges_from([(0, 1), (1, 2), (0, 0)])

    return [
        ("empty2", fnx.empty_graph(2), nx.empty_graph(2)),
        ("path5", fnx.path_graph(5), nx.path_graph(5)),
        ("star8", fnx.star_graph(7), nx.star_graph(7)),
        (
            "forest_path3_iso",
            fnx.disjoint_union(fnx.path_graph(3), fnx.empty_graph(1)),
            nx.disjoint_union(nx.path_graph(3), nx.empty_graph(1)),
        ),
        (
            "forest_two_paths",
            fnx.disjoint_union(fnx.path_graph(3), fnx.path_graph(2)),
            nx.disjoint_union(nx.path_graph(3), nx.path_graph(2)),
        ),
        ("triangle_tail_delegate", triangle_tail, nx_triangle_tail),
        ("self_loop_delegate", self_loop, nx_self_loop),
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
            "ordering_preserved": "forest components use connected-component order; singleton components omitted like NetworkX",
            "tie_breaking_unchanged": "forests have only k=1 non-singleton connected components",
            "floating_point": "N/A",
            "rng": "N/A",
        },
    }
    text = json.dumps(payload, sort_keys=True, indent=2)
    out.write_text(text + "\n", encoding="utf-8")
    print(hashlib.sha256((text + "\n").encode("utf-8")).hexdigest())
    if not payload["all_match"]:
        raise SystemExit("proof mismatch")


def _make_graph(kind: str, n: int, library):
    if kind == "path":
        return library.path_graph(n)
    if kind == "star":
        return library.star_graph(n - 1)
    if kind == "forest":
        return library.disjoint_union(library.path_graph(n), library.path_graph(n))
    raise ValueError(kind)


def time_case(kind: str, n: int, repeats: int, which: str) -> None:
    if which == "fnx":
        graph = _make_graph(kind, n, fnx)
        func = fnx.k_components
    elif which == "nx":
        graph = _make_graph(kind, n, nx)
        func = _nx_k_components
    else:
        raise ValueError(which)

    result = None
    start = time.perf_counter()
    for _ in range(repeats):
        result = func(graph)
    elapsed = time.perf_counter() - start
    payload = {
        "kind": kind,
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


def profile_case(kind: str, n: int, repeats: int, out: Path) -> None:
    graph = _make_graph(kind, n, fnx)
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
    time_parser.add_argument("--kind", choices=["path", "star", "forest"], default="star")
    time_parser.add_argument("--n", type=int, default=5000)
    time_parser.add_argument("--repeats", type=int, default=1)
    time_parser.add_argument("--which", choices=["fnx", "nx"], default="fnx")
    profile_parser = sub.add_parser("profile")
    profile_parser.add_argument("--kind", choices=["path", "star", "forest"], default="star")
    profile_parser.add_argument("--n", type=int, default=5000)
    profile_parser.add_argument("--repeats", type=int, default=1)
    profile_parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    if args.cmd == "proof":
        proof(args.out)
    elif args.cmd == "time":
        time_case(args.kind, args.n, args.repeats, args.which)
    else:
        profile_case(args.kind, args.n, args.repeats, args.out)


if __name__ == "__main__":
    main()
