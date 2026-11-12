#!/usr/bin/env python3
"""Benchmark and golden harness for br-r37-c1-pdn5j."""

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


def _exception_name(exc: BaseException) -> str:
    return f"{type(exc).__module__}.{type(exc).__name__}"


def _call_is_eulerian(lib: Any, graph: Any) -> dict[str, Any]:
    try:
        return {"ok": True, "value": bool(lib.is_eulerian(graph))}
    except Exception as exc:  # noqa: BLE001 - exception type is part of golden output.
        return {"ok": False, "exception": _exception_name(exc), "message": str(exc)}


def _fnx_from_nx(graph: nx.Graph) -> Any:
    return fnx.Graph(graph) if not graph.is_directed() else fnx.DiGraph(graph)


def _golden_cases() -> list[tuple[str, nx.Graph]]:
    cases: list[tuple[str, nx.Graph]] = []
    cases.append(("empty", nx.Graph()))
    cases.append(("single_isolated", nx.empty_graph(1)))
    self_loop = nx.Graph()
    self_loop.add_edge(0, 0)
    cases.append(("single_self_loop", self_loop))
    cases.append(("two_isolates", nx.empty_graph(2)))
    cases.append(("complete_5", nx.complete_graph(5)))
    cases.append(("complete_6", nx.complete_graph(6)))
    cases.append(("cycle_12", nx.cycle_graph(12)))
    cases.append(("path_12", nx.path_graph(12)))
    disconnected_cycles = nx.disjoint_union(nx.cycle_graph(4), nx.cycle_graph(6))
    cases.append(("disconnected_cycles", disconnected_cycles))
    looped_triangle = nx.complete_graph(3)
    looped_triangle.add_edge(0, 0)
    cases.append(("looped_triangle", looped_triangle))
    directed_cycle = nx.DiGraph([(0, 1), (1, 2), (2, 0)])
    cases.append(("directed_cycle", directed_cycle))
    directed_path = nx.DiGraph([(0, 1), (1, 2)])
    cases.append(("directed_path", directed_path))
    return cases


def _bench_graph(impl: str, case: str) -> Any:
    if case.startswith("complete_"):
        n = int(case.split("_", 1)[1])
        return fnx.complete_graph(n) if impl == "fnx" else nx.complete_graph(n)
    raise ValueError(f"unknown bench case: {case}")


def _bench_callable(impl: str, case: str) -> Callable[[], bool]:
    lib = fnx if impl == "fnx" else nx
    graph = _bench_graph(impl, case)
    return lambda: bool(lib.is_eulerian(graph))


def _sha_payload(payload: Any) -> str:
    data = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(data).hexdigest()


def golden(output: Path) -> None:
    payload: dict[str, Any] = {"cases": []}
    for name, nx_graph in _golden_cases():
        fnx_graph = _fnx_from_nx(nx_graph)
        nx_result = _call_is_eulerian(nx, nx_graph)
        fnx_result = _call_is_eulerian(fnx, fnx_graph)
        payload["cases"].append(
            {
                "case": name,
                "nx": nx_result,
                "fnx": fnx_result,
                "match": nx_result == fnx_result,
            }
        )
    payload["all_match"] = all(case["match"] for case in payload["cases"])
    payload["isomorphism"] = {
        "ordering": "N/A: scalar boolean or exception output only",
        "tie_breaking": "N/A",
        "floating_point": "N/A",
        "rng": "N/A",
        "self_loop_surface": "included in golden cases; FNX keeps existing fallback",
        "degree_order": "degree parity checked before connectivity, matching NetworkX",
    }
    payload["sha256"] = _sha_payload(payload)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(payload["sha256"])


def bench(impl: str, case: str, loops: int, repeats: int, output: Path) -> None:
    fn = _bench_callable(impl, case)
    for _ in range(5):
        fn()
    samples: list[float] = []
    gc_was_enabled = gc.isenabled()
    gc.disable()
    try:
        for _ in range(repeats):
            start = time.perf_counter()
            for _ in range(loops):
                fn()
            elapsed = time.perf_counter() - start
            samples.append(elapsed / loops)
    finally:
        if gc_was_enabled:
            gc.enable()
    payload = {
        "impl": impl,
        "case": case,
        "loops": loops,
        "repeats": repeats,
        "samples": samples,
        "mean": statistics.fmean(samples),
        "median": statistics.median(samples),
        "min": min(samples),
        "stdev": statistics.stdev(samples) if len(samples) > 1 else 0.0,
        "result": fn(),
    }
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(json.dumps(payload, sort_keys=True))


def profile(impl: str, case: str, loops: int, output: Path, limit: int) -> None:
    fn = _bench_callable(impl, case)
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
    subparsers = parser.add_subparsers(dest="command", required=True)

    golden_parser = subparsers.add_parser("golden")
    golden_parser.add_argument("--output", type=Path, required=True)

    bench_parser = subparsers.add_parser("bench")
    bench_parser.add_argument("--impl", choices=["fnx", "nx"], required=True)
    bench_parser.add_argument("--case", default="complete_601")
    bench_parser.add_argument("--loops", type=int, default=500)
    bench_parser.add_argument("--repeats", type=int, default=15)
    bench_parser.add_argument("--output", type=Path, required=True)

    profile_parser = subparsers.add_parser("profile")
    profile_parser.add_argument("--impl", choices=["fnx", "nx"], required=True)
    profile_parser.add_argument("--case", default="complete_601")
    profile_parser.add_argument("--loops", type=int, default=500)
    profile_parser.add_argument("--output", type=Path, required=True)
    profile_parser.add_argument("--limit", type=int, default=50)

    args = parser.parse_args()
    if args.command == "golden":
        golden(args.output)
    elif args.command == "bench":
        bench(args.impl, args.case, args.loops, args.repeats, args.output)
    elif args.command == "profile":
        profile(args.impl, args.case, args.loops, args.output, args.limit)


if __name__ == "__main__":
    main()
