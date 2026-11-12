#!/usr/bin/env python3
"""Adjacency-spectrum order/parity harness for br-r37-c1-04z53.9112."""

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


def make_pair(case: str, n: int) -> tuple[Any, Any]:
    if case == "path":
        nx_graph = nx.path_graph(n)
    elif case == "cycle":
        nx_graph = nx.cycle_graph(n)
    elif case == "complete":
        nx_graph = nx.complete_graph(n)
    elif case == "ba":
        nx_graph = nx.barabasi_albert_graph(n, min(4, max(1, n - 1)), seed=17)
    elif case == "directed_cycle":
        nx_graph = nx.DiGraph((i, (i + 1) % n) for i in range(n))
    else:
        raise ValueError(f"unknown case: {case}")

    graph_type = fnx.DiGraph if nx_graph.is_directed() else fnx.Graph
    fnx_graph = graph_type()
    fnx_graph.add_nodes_from(nx_graph.nodes())
    for u, v in nx_graph.edges():
        weight = 1.0 + ((int(u) * 131 + int(v) * 17) % 29) / 11.0
        nx_graph[u][v]["weight"] = weight
        fnx_graph.add_edge(u, v, weight=weight)
    return fnx_graph, nx_graph


def complex_payload(values: Any, digits: int = 17) -> list[str]:
    fmt = f".{digits}g"
    return [
        f"{float(np.real(value)):{fmt}}:{float(np.imag(value)):{fmt}}"
        for value in values
    ]


def quantized_complex_payload(values: Any) -> list[str]:
    payload: list[str] = []
    for value in values:
        real = float(np.real(value))
        imag = float(np.imag(value))
        if abs(real) < 5.0e-10:
            real = 0.0
        if abs(imag) < 5.0e-10:
            imag = 0.0
        payload.append(f"{real:.10f}:{imag:.10f}")
    return payload


def sorted_complex(values: Any) -> list[complex]:
    return sorted((complex(value) for value in values), key=lambda z: (z.real, z.imag))


def native_adjacency_spectrum(graph: Any) -> np.ndarray:
    native = getattr(fnx._fnx, "real_general_eigvals_rust", None)
    if native is None:
        raise RuntimeError("real_general_eigvals_rust is not available")
    matrix = fnx.adjacency_matrix(graph, weight="weight").toarray()
    flat = [float(value) for value in np.ascontiguousarray(matrix, dtype=np.float64).ravel()]
    values = native(flat, matrix.shape[0])
    if values is None:
        raise RuntimeError("real_general_eigvals_rust did not converge")
    return np.asarray([complex(real, imag) for real, imag in values], dtype=np.complex128)


def public_adjacency_spectrum(graph: Any) -> np.ndarray:
    return np.asarray(fnx.adjacency_spectrum(graph, weight="weight"), dtype=np.complex128)


def golden(cases: list[str], output: Path | None) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    public_quantized: list[dict[str, Any]] = []
    native_quantized: list[dict[str, Any]] = []
    public_sorted_quantized: list[dict[str, Any]] = []
    native_sorted_quantized: list[dict[str, Any]] = []
    max_sorted_abs_delta = 0.0
    all_public_raw_match = True
    all_native_raw_match = True
    all_native_sorted_match = True

    for spec in cases:
        case, n_text = spec.split(":", 1)
        n = int(n_text)
        fnx_graph, nx_graph = make_pair(case, n)
        public_values = public_adjacency_spectrum(fnx_graph)
        nx_values = np.asarray(nx_adjacency_spectrum(nx_graph, weight="weight"))
        native_values = native_adjacency_spectrum(fnx_graph)

        sorted_public = sorted_complex(public_values)
        sorted_native = sorted_complex(native_values)
        sorted_deltas = [
            abs(left - right)
            for left, right in zip(sorted_public, sorted_native, strict=True)
        ]
        max_case_delta = max(sorted_deltas) if sorted_deltas else 0.0
        max_sorted_abs_delta = max(max_sorted_abs_delta, float(max_case_delta))

        public_raw_match = bool(np.allclose(public_values, nx_values, rtol=0.0, atol=0.0))
        native_raw_match = bool(np.allclose(native_values, nx_values, rtol=1.0e-8, atol=1.0e-8))
        native_sorted_match = bool(
            np.allclose(sorted_native, sorted_complex(nx_values), rtol=1.0e-8, atol=1.0e-8)
        )
        all_public_raw_match = all_public_raw_match and public_raw_match
        all_native_raw_match = all_native_raw_match and native_raw_match
        all_native_sorted_match = all_native_sorted_match and native_sorted_match

        records.append(
            {
                "case": case,
                "n": n,
                "native": complex_payload(native_values),
                "native_raw_match": native_raw_match,
                "native_sorted_match": native_sorted_match,
                "networkx": complex_payload(nx_values),
                "public": complex_payload(public_values),
                "public_raw_match": public_raw_match,
                "sorted_abs_delta": float(max_case_delta),
            }
        )
        public_quantized.append(
            {"case": case, "n": n, "values": quantized_complex_payload(public_values)}
        )
        native_quantized.append(
            {"case": case, "n": n, "values": quantized_complex_payload(native_values)}
        )
        public_sorted_quantized.append(
            {
                "case": case,
                "n": n,
                "values": quantized_complex_payload(sorted_public),
            }
        )
        native_sorted_quantized.append(
            {
                "case": case,
                "n": n,
                "values": quantized_complex_payload(sorted_native),
            }
        )

    def digest(value: Any) -> str:
        encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(encoded).hexdigest()

    result = {
        "all_native_raw_match": all_native_raw_match,
        "all_native_sorted_match": all_native_sorted_match,
        "all_public_raw_match": all_public_raw_match,
        "cases": cases,
        "max_sorted_abs_delta": max_sorted_abs_delta,
        "native_raw_sha256": digest(native_quantized),
        "native_sorted_sha256": digest(native_sorted_quantized),
        "networkx_raw_sha256": digest(public_quantized),
        "networkx_sorted_sha256": digest(public_sorted_quantized),
        "records": records,
    }
    if output is not None:
        output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    return result


def bench_once(impl: str, case: str, n: int, loops: int) -> float:
    fnx_graph, nx_graph = make_pair(case, n)
    if impl == "fnx":
        func = lambda: public_adjacency_spectrum(fnx_graph)
    elif impl == "nx":
        func = lambda: nx_adjacency_spectrum(nx_graph, weight="weight")
    elif impl == "native":
        func = lambda: native_adjacency_spectrum(fnx_graph)
    else:
        raise ValueError(f"unknown impl: {impl}")

    func()
    start = time.perf_counter()
    for _ in range(loops):
        func()
    return time.perf_counter() - start


def bench(
    impl: str, case: str, n: int, loops: int, samples: int, output: Path | None
) -> dict[str, Any]:
    runs = [bench_once(impl, case, n, loops) for _ in range(samples)]
    per_call = [elapsed / loops for elapsed in runs]
    result = {
        "case": case,
        "impl": impl,
        "loops": loops,
        "mean_per_call_seconds": statistics.fmean(per_call),
        "median_per_call_seconds": statistics.median(per_call),
        "n": n,
        "per_call_seconds": per_call,
        "samples": samples,
        "seconds": runs,
    }
    if output is not None:
        output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    return result


def profile(impl: str, case: str, n: int, loops: int, output: Path) -> dict[str, Any]:
    profiler = cProfile.Profile()
    profiler.enable()
    elapsed = bench_once(impl, case, n, loops)
    profiler.disable()

    summary = io.StringIO()
    stats = pstats.Stats(profiler, stream=summary).strip_dirs().sort_stats("cumtime")
    stats.print_stats(35)
    output.write_text(summary.getvalue())
    return {
        "case": case,
        "elapsed_seconds": elapsed,
        "impl": impl,
        "loops": loops,
        "n": n,
        "profile": str(output),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)

    golden_parser = sub.add_parser("golden")
    golden_parser.add_argument(
        "--cases", default="path:5,cycle:6,complete:5,ba:160,ba:400,directed_cycle:8"
    )
    golden_parser.add_argument("--output", type=Path)

    bench_parser = sub.add_parser("bench")
    bench_parser.add_argument("--impl", choices=("fnx", "nx", "native"), required=True)
    bench_parser.add_argument("--case", default="ba")
    bench_parser.add_argument("--n", type=int, default=400)
    bench_parser.add_argument("--loops", type=int, default=1)
    bench_parser.add_argument("--samples", type=int, default=5)
    bench_parser.add_argument("--output", type=Path)

    profile_parser = sub.add_parser("profile")
    profile_parser.add_argument("--impl", choices=("fnx", "nx", "native"), required=True)
    profile_parser.add_argument("--case", default="ba")
    profile_parser.add_argument("--n", type=int, default=400)
    profile_parser.add_argument("--loops", type=int, default=3)
    profile_parser.add_argument("--output", type=Path, required=True)

    args = parser.parse_args()
    if args.cmd == "golden":
        cases = [value for value in args.cases.split(",") if value]
        result = golden(cases, args.output)
    elif args.cmd == "bench":
        result = bench(args.impl, args.case, args.n, args.loops, args.samples, args.output)
    else:
        result = profile(args.impl, args.case, args.n, args.loops, args.output)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
