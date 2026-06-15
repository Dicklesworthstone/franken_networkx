#!/usr/bin/env python3
"""Baseline, profile, and proof harness for br-r37-c1-04z53.9112."""

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
from typing import Any

import networkx as nx
import numpy as np

import franken_networkx as fnx


nx_adjacency_spectrum = getattr(
    nx.adjacency_spectrum, "orig_func", nx.adjacency_spectrum
)


def graph_pair(case: str, n: int) -> tuple[Any, Any]:
    if case == "path":
        nx_graph = nx.path_graph(n)
    elif case == "cycle":
        nx_graph = nx.cycle_graph(n)
    elif case == "ba":
        nx_graph = nx.barabasi_albert_graph(n, min(4, n - 1), seed=17)
    elif case == "weighted_ba":
        nx_graph = nx.barabasi_albert_graph(n, min(4, n - 1), seed=17)
        for u, v in nx_graph.edges():
            nx_graph[u][v]["weight"] = 1.0 + ((u * 131 + v * 17) % 29) / 11.0
    elif case == "directed_cycle":
        nx_graph = nx.DiGraph((i, (i + 1) % n) for i in range(n))
    else:
        raise ValueError(f"unknown case: {case}")

    if nx_graph.is_directed():
        fnx_graph = fnx.DiGraph()
    else:
        fnx_graph = fnx.Graph()
    fnx_graph.add_nodes_from(nx_graph.nodes())
    for u, v, attrs in nx_graph.edges(data=True):
        fnx_graph.add_edge(u, v, **dict(attrs))
    return fnx_graph, nx_graph


def _rounded_complex(values: np.ndarray) -> list[tuple[float, float]]:
    array = np.asarray(values, dtype=np.complex128)
    return [
        (round(float(value.real), 12), round(float(value.imag), 12))
        for value in array
    ]


def _sha(payload: object) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _spectrum(impl: str, graph: Any, weight: str | None) -> np.ndarray:
    if impl == "fnx":
        return np.asarray(fnx.adjacency_spectrum(graph, weight=weight))
    if impl == "nx":
        return np.asarray(nx_adjacency_spectrum(graph, weight=weight))
    raise ValueError(f"unknown impl: {impl}")


def golden(cases: list[str], sizes: list[int], output: Path | None) -> dict[str, Any]:
    records = []
    raw_fnx_digest = []
    raw_nx_digest = []
    sorted_fnx_digest = []
    sorted_nx_digest = []
    max_sorted_abs_delta = 0.0
    raw_order_matches = True
    dtype_matches = True

    for case in cases:
        for n in sizes:
            if n < 2:
                continue
            fnx_graph, nx_graph = graph_pair(case, n)
            weight = "weight"
            fnx_values = _spectrum("fnx", fnx_graph, weight)
            nx_values = _spectrum("nx", nx_graph, weight)
            fnx_sorted = np.sort_complex(fnx_values)
            nx_sorted = np.sort_complex(nx_values)
            sorted_delta = np.abs(fnx_sorted - nx_sorted)
            if sorted_delta.size:
                max_sorted_abs_delta = max(
                    max_sorted_abs_delta, float(np.max(sorted_delta))
                )
            raw_match = bool(
                fnx_values.shape == nx_values.shape
                and np.allclose(fnx_values, nx_values, rtol=1.0e-10, atol=1.0e-10)
            )
            sorted_match = bool(
                fnx_sorted.shape == nx_sorted.shape
                and np.allclose(fnx_sorted, nx_sorted, rtol=1.0e-10, atol=1.0e-10)
            )
            dtype_match = str(fnx_values.dtype) == str(nx_values.dtype) == "complex128"
            raw_order_matches = raw_order_matches and raw_match
            dtype_matches = dtype_matches and dtype_match
            record = {
                "case": case,
                "n": n,
                "fnx_dtype": str(fnx_values.dtype),
                "nx_dtype": str(nx_values.dtype),
                "raw_order_match": raw_match,
                "sorted_match": sorted_match,
                "dtype_match": dtype_match,
                "fnx_raw": _rounded_complex(fnx_values),
                "nx_raw": _rounded_complex(nx_values),
            }
            records.append(record)
            identity = {"case": case, "n": n}
            raw_fnx_digest.append({**identity, "values": record["fnx_raw"]})
            raw_nx_digest.append({**identity, "values": record["nx_raw"]})
            sorted_fnx_digest.append(
                {**identity, "values": _rounded_complex(fnx_sorted)}
            )
            sorted_nx_digest.append({**identity, "values": _rounded_complex(nx_sorted)})

    result = {
        "bead": "br-r37-c1-04z53.9112",
        "cases": cases,
        "sizes": sizes,
        "dtype_matches": dtype_matches,
        "raw_order_matches": raw_order_matches,
        "max_sorted_abs_delta": max_sorted_abs_delta,
        "fnx_raw_sha256": _sha(raw_fnx_digest),
        "nx_raw_sha256": _sha(raw_nx_digest),
        "fnx_sorted_sha256": _sha(sorted_fnx_digest),
        "nx_sorted_sha256": _sha(sorted_nx_digest),
        "records": records,
    }
    if output is not None:
        output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    return result


def bench_once(impl: str, case: str, n: int, loops: int, weight: str | None) -> float:
    fnx_graph, nx_graph = graph_pair(case, n)
    graph = fnx_graph if impl == "fnx" else nx_graph
    start = time.perf_counter()
    for _ in range(loops):
        _spectrum(impl, graph, weight)
    return time.perf_counter() - start


def bench(
    impl: str,
    case: str,
    n: int,
    loops: int,
    samples: int,
    output: Path | None,
) -> dict[str, Any]:
    weight = "weight"
    runs = [bench_once(impl, case, n, loops, weight) for _ in range(samples)]
    per_loop = [elapsed / loops for elapsed in runs]
    result = {
        "bead": "br-r37-c1-04z53.9112",
        "impl": impl,
        "case": case,
        "n": n,
        "loops": loops,
        "samples": samples,
        "seconds": runs,
        "per_loop_seconds": per_loop,
        "mean_per_loop_seconds": statistics.fmean(per_loop),
        "median_per_loop_seconds": statistics.median(per_loop),
    }
    if output is not None:
        output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    return result


def profile(impl: str, case: str, n: int, loops: int, output: Path) -> dict[str, Any]:
    _ = bench_once(impl, case, n, 1, "weight")
    profiler = cProfile.Profile()
    profiler.enable()
    elapsed = bench_once(impl, case, n, loops, "weight")
    profiler.disable()
    stream = io.StringIO()
    pstats.Stats(profiler, stream=stream).sort_stats("cumtime").print_stats(40)
    output.write_text(stream.getvalue())
    return {
        "bead": "br-r37-c1-04z53.9112",
        "impl": impl,
        "case": case,
        "n": n,
        "loops": loops,
        "elapsed_seconds": elapsed,
    }


def scipy_order_probe(cases: list[str], sizes: list[int], output: Path | None) -> dict[str, Any]:
    records = []
    for case in cases:
        if case == "directed_cycle":
            continue
        for n in sizes:
            _, nx_graph = graph_pair(case, n)
            matrix = nx.to_numpy_array(nx_graph, weight="weight", dtype=np.float64)
            scipy_values = np.asarray(nx_adjacency_spectrum(nx_graph), dtype=np.complex128)
            symmetric_values = np.linalg.eigvalsh(matrix).astype(np.complex128)
            records.append(
                {
                    "case": case,
                    "n": n,
                    "scipy_matches_sorted_eigvalsh_order": bool(
                        scipy_values.shape == symmetric_values.shape
                        and np.allclose(
                            scipy_values,
                            symmetric_values,
                            rtol=1.0e-10,
                            atol=1.0e-10,
                        )
                    ),
                    "sorted_values_match": bool(
                        np.allclose(
                            np.sort_complex(scipy_values),
                            np.sort_complex(symmetric_values),
                            rtol=1.0e-10,
                            atol=1.0e-10,
                        )
                    ),
                    "scipy_first_values": _rounded_complex(scipy_values[:8]),
                    "symmetric_first_values": _rounded_complex(symmetric_values[:8]),
                }
            )
    result = {"bead": "br-r37-c1-04z53.9112", "records": records}
    if output is not None:
        output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    golden_parser = subparsers.add_parser("golden")
    golden_parser.add_argument("--cases", nargs="+", default=["path", "cycle", "ba", "weighted_ba", "directed_cycle"])
    golden_parser.add_argument("--sizes", nargs="+", type=int, default=[4, 8, 32, 96])
    golden_parser.add_argument("--output", type=Path)

    bench_parser = subparsers.add_parser("bench")
    bench_parser.add_argument("--impl", choices=["fnx", "nx"], required=True)
    bench_parser.add_argument("--case", default="weighted_ba")
    bench_parser.add_argument("--n", type=int, default=160)
    bench_parser.add_argument("--loops", type=int, default=3)
    bench_parser.add_argument("--samples", type=int, default=5)
    bench_parser.add_argument("--output", type=Path)

    profile_parser = subparsers.add_parser("profile")
    profile_parser.add_argument("--impl", choices=["fnx", "nx"], required=True)
    profile_parser.add_argument("--case", default="weighted_ba")
    profile_parser.add_argument("--n", type=int, default=160)
    profile_parser.add_argument("--loops", type=int, default=3)
    profile_parser.add_argument("--output", type=Path, required=True)

    order_parser = subparsers.add_parser("scipy-order")
    order_parser.add_argument("--cases", nargs="+", default=["path", "cycle", "ba", "weighted_ba"])
    order_parser.add_argument("--sizes", nargs="+", type=int, default=[4, 8, 32, 96])
    order_parser.add_argument("--output", type=Path)

    args = parser.parse_args()
    if args.command == "golden":
        result = golden(args.cases, args.sizes, args.output)
    elif args.command == "bench":
        result = bench(args.impl, args.case, args.n, args.loops, args.samples, args.output)
    elif args.command == "profile":
        result = profile(args.impl, args.case, args.n, args.loops, args.output)
    elif args.command == "scipy-order":
        result = scipy_order_probe(args.cases, args.sizes, args.output)
    else:
        raise AssertionError(args.command)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
