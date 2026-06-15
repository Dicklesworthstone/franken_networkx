#!/usr/bin/env python3
"""Baseline, proof, and timing harness for br-r37-c1-04z53.9109."""

from __future__ import annotations

import argparse
import cProfile
import hashlib
import io
import json
import math
import pstats
import statistics
import time
from pathlib import Path
from typing import Any

import networkx as nx

import franken_networkx as fnx


nx_laplacian_spectrum = getattr(
    nx.laplacian_spectrum, "orig_func", nx.laplacian_spectrum
)


def make_pair(n: int) -> tuple[Any, Any]:
    if n < 6:
        nx_graph = nx.path_graph(n)
    else:
        nx_graph = nx.barabasi_albert_graph(n, 4, seed=17)
    fnx_graph = fnx.Graph()
    fnx_graph.add_nodes_from(nx_graph.nodes())
    for u, v in nx_graph.edges():
        weight = 1.0 + ((u * 131 + v * 17) % 29) / 11.0
        nx_graph[u][v]["weight"] = weight
        fnx_graph.add_edge(u, v, weight=weight)
    return fnx_graph, nx_graph


def _float_payload(values: Any) -> list[str]:
    return [format(float(value), ".17g") for value in values]


def native_laplacian_spectrum(graph: Any) -> Any:
    matrix = fnx.laplacian_matrix(graph, weight="weight").toarray()
    native = getattr(fnx._fnx, "symmetric_eigvals_rust", None)
    if native is None:
        raise RuntimeError("symmetric_eigvals_rust is not available")
    values = native([float(value) for value in matrix.ravel(order="C")], matrix.shape[0])
    if values is None:
        raise RuntimeError("symmetric_eigvals_rust did not converge")
    return values


def golden(cases: list[int], output: Path | None) -> dict[str, Any]:
    records = []
    max_abs_delta = 0.0
    max_rel_delta = 0.0
    for n in cases:
        fnx_graph, nx_graph = make_pair(n)
        fnx_values = fnx.laplacian_spectrum(fnx_graph, weight="weight")
        nx_values = nx_laplacian_spectrum(nx_graph, weight="weight")
        deltas = [
            abs(float(fnx_value) - float(nx_value))
            for fnx_value, nx_value in zip(fnx_values, nx_values, strict=True)
        ]
        rels = [
            delta / max(abs(float(nx_value)), 1.0)
            for delta, nx_value in zip(deltas, nx_values, strict=True)
        ]
        if deltas:
            max_abs_delta = max(max_abs_delta, max(deltas))
            max_rel_delta = max(max_rel_delta, max(rels))
        records.append(
            {
                "n": n,
                "fnx": _float_payload(fnx_values),
                "nx": _float_payload(nx_values),
            }
        )

    encoded = json.dumps(records, sort_keys=True, separators=(",", ":")).encode()
    result = {
        "cases": cases,
        "max_abs_delta": max_abs_delta,
        "max_rel_delta": max_rel_delta,
        "sha256": hashlib.sha256(encoded).hexdigest(),
        "within_1e_8": max_abs_delta <= 1.0e-8 and max_rel_delta <= 1.0e-10,
    }
    if output is not None:
        output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    return result


def bench_once(impl: str, n: int, loops: int) -> float:
    fnx_graph, nx_graph = make_pair(n)
    if impl == "fnx":
        func = lambda: fnx.laplacian_spectrum(fnx_graph, weight="weight")
    elif impl == "nx":
        func = lambda: nx_laplacian_spectrum(nx_graph, weight="weight")
    elif impl == "native":
        func = lambda: native_laplacian_spectrum(fnx_graph)
    else:
        raise ValueError(f"unknown impl: {impl}")

    func()
    start = time.perf_counter()
    for _ in range(loops):
        func()
    return time.perf_counter() - start


def bench(impl: str, n: int, loops: int, samples: int, output: Path | None) -> dict[str, Any]:
    runs = [bench_once(impl, n, loops) for _ in range(samples)]
    per_call = [elapsed / loops for elapsed in runs]
    result = {
        "impl": impl,
        "n": n,
        "loops": loops,
        "samples": samples,
        "seconds": runs,
        "per_call_seconds": per_call,
        "median_per_call_seconds": statistics.median(per_call),
        "mean_per_call_seconds": statistics.fmean(per_call),
    }
    if output is not None:
        output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    return result


def profile(impl: str, n: int, loops: int, output: Path) -> dict[str, Any]:
    profiler = cProfile.Profile()
    profiler.enable()
    elapsed = bench_once(impl, n, loops)
    profiler.disable()

    summary = io.StringIO()
    stats = pstats.Stats(profiler, stream=summary).strip_dirs().sort_stats("cumtime")
    stats.print_stats(35)
    output.write_text(summary.getvalue())
    return {
        "elapsed_seconds": elapsed,
        "impl": impl,
        "loops": loops,
        "n": n,
        "profile": str(output),
    }


def raw_native_check(n: int, tolerance: float) -> dict[str, Any]:
    fnx_graph, _ = make_pair(n)
    matrix = fnx.laplacian_matrix(fnx_graph, weight="weight").toarray()
    native = getattr(fnx._fnx, "symmetric_eigvals_rust", None)
    if native is None:
        return {"available": False}
    got = native([float(value) for value in matrix.ravel(order="C")], matrix.shape[0])
    if got is None:
        return {"available": True, "converged": False}
    ref = fnx.laplacian_spectrum(fnx_graph, weight="weight")
    deltas = [abs(float(a) - float(b)) for a, b in zip(got, ref, strict=True)]
    max_abs = max(deltas) if deltas else 0.0
    return {
        "available": True,
        "converged": True,
        "max_abs_delta_vs_public": max_abs,
        "within_tolerance": bool(max_abs <= tolerance or math.isclose(max_abs, 0.0)),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)

    golden_parser = sub.add_parser("golden")
    golden_parser.add_argument("--cases", default="2,5,8,32,96")
    golden_parser.add_argument("--output", type=Path)

    bench_parser = sub.add_parser("bench")
    bench_parser.add_argument("--impl", choices=("fnx", "nx", "native"), required=True)
    bench_parser.add_argument("--n", type=int, default=180)
    bench_parser.add_argument("--loops", type=int, default=3)
    bench_parser.add_argument("--samples", type=int, default=7)
    bench_parser.add_argument("--output", type=Path)

    profile_parser = sub.add_parser("profile")
    profile_parser.add_argument("--impl", choices=("fnx", "nx", "native"), required=True)
    profile_parser.add_argument("--n", type=int, default=180)
    profile_parser.add_argument("--loops", type=int, default=3)
    profile_parser.add_argument("--output", type=Path, required=True)

    raw_parser = sub.add_parser("raw-native-check")
    raw_parser.add_argument("--n", type=int, default=96)
    raw_parser.add_argument("--tolerance", type=float, default=1.0e-8)

    args = parser.parse_args()
    if args.cmd == "golden":
        cases = [int(value) for value in args.cases.split(",") if value]
        result = golden(cases, args.output)
    elif args.cmd == "bench":
        result = bench(args.impl, args.n, args.loops, args.samples, args.output)
    elif args.cmd == "profile":
        result = profile(args.impl, args.n, args.loops, args.output)
    else:
        result = raw_native_check(args.n, args.tolerance)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
