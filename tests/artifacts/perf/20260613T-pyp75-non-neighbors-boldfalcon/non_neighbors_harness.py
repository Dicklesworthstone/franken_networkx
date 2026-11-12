#!/usr/bin/env python3
"""Benchmark and golden harness for br-r37-c1-pyp75."""

from __future__ import annotations

import argparse
import cProfile
import gc
import hashlib
import json
import pstats
import statistics
import time
from pathlib import Path
from typing import Any, Callable

import franken_networkx as fnx
import networkx as nx

_NX_NON_NEIGHBORS = getattr(nx.non_neighbors, "orig_func", nx.non_neighbors)


def _exception_name(exc: BaseException) -> str:
    return f"{type(exc).__module__}.{type(exc).__name__}"


def _norm_value(value: Any) -> str:
    return f"{type(value).__name__}:{value!r}"


def _norm_set(values: set[Any]) -> list[str]:
    return sorted(_norm_value(value) for value in values)


def _call_non_neighbors(lib: Any, graph: Any, node: Any) -> dict[str, Any]:
    try:
        if lib is nx:
            value = set(_NX_NON_NEIGHBORS(graph, node))
        else:
            value = set(lib.non_neighbors(graph, node))
        return {"ok": True, "value": _norm_set(value)}
    except Exception as exc:  # noqa: BLE001 - exception type is golden data.
        return {"ok": False, "exception": _exception_name(exc), "message": str(exc)}


def _edge_rows(n: int, degree: int) -> list[tuple[int, int]]:
    edges: list[tuple[int, int]] = []
    for u in range(n):
        for step in range(1, degree + 1):
            edges.append((u, (u + step * 7) % n))
    return edges


def _make_graph(kind: str, n: int, degree: int) -> tuple[Any, Any]:
    edges = _edge_rows(n, degree)
    if kind == "digraph":
        nx_graph = nx.DiGraph()
        fnx_graph = fnx.DiGraph()
    elif kind == "multidigraph":
        nx_graph = nx.MultiDiGraph()
        fnx_graph = fnx.MultiDiGraph()
    else:
        raise ValueError(kind)
    nx_graph.add_nodes_from(range(n))
    fnx_graph.add_nodes_from(range(n))
    nx_graph.add_edges_from(edges)
    fnx_graph.add_edges_from(edges)
    return fnx_graph, nx_graph


def _small_cases() -> list[tuple[str, Any, Any, Any]]:
    cases: list[tuple[str, Any, Any, Any]] = []
    for kind in ("digraph", "multidigraph"):
        fnx_graph, nx_graph = _make_graph(kind, 12, 2)
        cases.append((f"{kind}_int", fnx_graph, nx_graph, 0))

    fnx_dg = fnx.DiGraph()
    nx_dg = nx.DiGraph()
    fnx_dg.add_edges_from([("a", "b"), ("a", "c"), ("d", "a")])
    nx_dg.add_edges_from([("a", "b"), ("a", "c"), ("d", "a")])
    cases.append(("digraph_str", fnx_dg, nx_dg, "a"))

    fnx_mdg = fnx.MultiDiGraph()
    nx_mdg = nx.MultiDiGraph()
    fnx_mdg.add_edges_from([(0, 1), (0, 1), (2, 0), (2, 3)])
    nx_mdg.add_edges_from([(0, 1), (0, 1), (2, 0), (2, 3)])
    cases.append(("multidigraph_parallel", fnx_mdg, nx_mdg, 0))
    cases.append(("missing_node", fnx_mdg, nx_mdg, 99))
    return cases


def _sha_payload(payload: Any) -> str:
    data = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(data).hexdigest()


def golden(output: Path) -> None:
    payload: dict[str, Any] = {"cases": []}
    for name, fnx_graph, nx_graph, node in _small_cases():
        fnx_result = _call_non_neighbors(fnx, fnx_graph, node)
        nx_result = _call_non_neighbors(nx, nx_graph, node)
        payload["cases"].append(
            {
                "case": name,
                "fnx": fnx_result,
                "match": fnx_result == nx_result,
                "node": _norm_value(node),
                "nx": nx_result,
            }
        )
    payload["all_match"] = all(case["match"] for case in payload["cases"])
    payload["isomorphism"] = {
        "ordering": "N/A: public output is a set; payload sorts only for hashing",
        "tie_breaking": "N/A",
        "floating_point": "N/A",
        "rng": "N/A",
        "successor_semantics": "directed non_neighbors subtracts successors only, matching NetworkX",
    }
    payload["sha256"] = _sha_payload(payload)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(payload["sha256"])


def _bench_callable(impl: str, kind: str, n: int, degree: int, node: int) -> Callable[[], set[Any]]:
    fnx_graph, nx_graph = _make_graph(kind, n, degree)
    if impl == "fnx":
        return lambda: set(fnx.non_neighbors(fnx_graph, node))
    if impl == "nx":
        return lambda: set(_NX_NON_NEIGHBORS(nx_graph, node))
    raise ValueError(impl)


def bench(impl: str, kind: str, n: int, degree: int, node: int, loops: int, repeats: int, output: Path) -> None:
    fn = _bench_callable(impl, kind, n, degree, node)
    for _ in range(5):
        fn()
    samples: list[float] = []
    gc_was_enabled = gc.isenabled()
    gc.disable()
    try:
        for _ in range(repeats):
            start = time.perf_counter()
            result: set[Any] = set()
            for _ in range(loops):
                result = fn()
            elapsed = time.perf_counter() - start
            samples.append(elapsed / loops)
    finally:
        if gc_was_enabled:
            gc.enable()
    payload = {
        "degree": degree,
        "digest": hashlib.sha256(json.dumps(_norm_set(result)).encode()).hexdigest(),
        "impl": impl,
        "kind": kind,
        "loops": loops,
        "mean": statistics.fmean(samples),
        "median": statistics.median(samples),
        "min": min(samples),
        "n": n,
        "node": node,
        "repeats": repeats,
        "samples": samples,
        "stdev": statistics.stdev(samples) if len(samples) > 1 else 0.0,
    }
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(json.dumps(payload, sort_keys=True))


def profile(impl: str, kind: str, n: int, degree: int, node: int, loops: int, output: Path, limit: int) -> None:
    fn = _bench_callable(impl, kind, n, degree, node)
    profiler = cProfile.Profile()
    profiler.enable()
    for _ in range(loops):
        fn()
    profiler.disable()
    with output.open("w") as handle:
        stats = pstats.Stats(profiler, stream=handle).sort_stats("cumulative")
        stats.print_stats(limit)


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    golden_parser = sub.add_parser("golden")
    golden_parser.add_argument("--output", type=Path, required=True)

    bench_parser = sub.add_parser("bench")
    bench_parser.add_argument("--impl", choices=["fnx", "nx"], required=True)
    bench_parser.add_argument("--kind", choices=["digraph", "multidigraph"], required=True)
    bench_parser.add_argument("--n", type=int, default=1500)
    bench_parser.add_argument("--degree", type=int, default=3)
    bench_parser.add_argument("--node", type=int, default=0)
    bench_parser.add_argument("--loops", type=int, default=500)
    bench_parser.add_argument("--repeats", type=int, default=15)
    bench_parser.add_argument("--output", type=Path, required=True)

    profile_parser = sub.add_parser("profile")
    profile_parser.add_argument("--impl", choices=["fnx", "nx"], required=True)
    profile_parser.add_argument("--kind", choices=["digraph", "multidigraph"], required=True)
    profile_parser.add_argument("--n", type=int, default=1500)
    profile_parser.add_argument("--degree", type=int, default=3)
    profile_parser.add_argument("--node", type=int, default=0)
    profile_parser.add_argument("--loops", type=int, default=1000)
    profile_parser.add_argument("--output", type=Path, required=True)
    profile_parser.add_argument("--limit", type=int, default=50)

    args = parser.parse_args()
    if args.command == "golden":
        golden(args.output)
    elif args.command == "bench":
        bench(args.impl, args.kind, args.n, args.degree, args.node, args.loops, args.repeats, args.output)
    elif args.command == "profile":
        profile(args.impl, args.kind, args.n, args.degree, args.node, args.loops, args.output, args.limit)


if __name__ == "__main__":
    main()
