#!/usr/bin/env python3
"""Baseline, profile, and proof harness for br-r37-c1-04z53.9111."""

from __future__ import annotations

import argparse
import cProfile
import hashlib
import hmac
import io
import json
import math
import pstats
import statistics
import time
from pathlib import Path
from typing import Any

import networkx as nx
import numpy as np

import franken_networkx as fnx


nx_laplacian_spectrum = getattr(
    nx.laplacian_spectrum, "orig_func", nx.laplacian_spectrum
)


def dense_symmetric_matrix(n: int) -> np.ndarray:
    rng = np.random.default_rng(9111 + n)
    matrix = rng.standard_normal((n, n), dtype=np.float64)
    matrix = (matrix + matrix.T) * 0.5
    diagonal = np.linspace(0.25, 2.25, n, dtype=np.float64)
    matrix[np.diag_indices(n)] += diagonal
    return np.ascontiguousarray(matrix)


def weighted_graph_pair(n: int) -> tuple[Any, Any]:
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


def laplacian_matrix(n: int) -> np.ndarray:
    fnx_graph, _ = weighted_graph_pair(n)
    return np.ascontiguousarray(
        fnx.laplacian_matrix(fnx_graph, weight="weight").toarray(), dtype=np.float64
    )


def matrix_for(case: str, n: int) -> np.ndarray:
    if case == "dense":
        return dense_symmetric_matrix(n)
    if case == "laplacian":
        return laplacian_matrix(n)
    raise ValueError(f"unknown case: {case}")


def native_eigvals(payload: list[float], n: int) -> list[float]:
    native = getattr(fnx._fnx, "symmetric_eigvals_rust", None)
    if native is None:
        raise RuntimeError("symmetric_eigvals_rust is not available")
    values = native(payload, n)
    if values is None:
        raise RuntimeError("symmetric_eigvals_rust did not converge")
    return values


def bench_raw_once(impl: str, case: str, n: int, loops: int) -> float:
    matrix = matrix_for(case, n)
    payload = [float(value) for value in matrix.ravel(order="C")]
    if impl == "native":
        func = lambda: native_eigvals(payload, n)
    elif impl == "numpy":
        func = lambda: np.linalg.eigvalsh(matrix)
    else:
        raise ValueError(f"unknown raw impl: {impl}")

    values = func()
    checksum = float(np.asarray(values, dtype=np.float64)[0])
    start = time.perf_counter()
    for _ in range(loops):
        values = func()
        checksum += float(np.asarray(values, dtype=np.float64)[-1])
    elapsed = time.perf_counter() - start
    if not math.isfinite(checksum):
        raise AssertionError(checksum)
    return elapsed


def bench_raw(
    impl: str,
    case: str,
    n: int,
    loops: int,
    samples: int,
    output: Path | None,
) -> dict[str, Any]:
    runs = [bench_raw_once(impl, case, n, loops) for _ in range(samples)]
    per_loop = [elapsed / loops for elapsed in runs]
    result = {
        "case": case,
        "impl": impl,
        "loops": loops,
        "mean_per_loop_seconds": statistics.fmean(per_loop),
        "median_per_loop_seconds": statistics.median(per_loop),
        "n": n,
        "per_loop_seconds": per_loop,
        "samples": samples,
        "seconds": runs,
    }
    if output is not None:
        output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    return result


def bench_spectrum_once(impl: str, n: int, loops: int) -> float:
    fnx_graph, nx_graph = weighted_graph_pair(n)
    if impl == "fnx":
        func = lambda: fnx.laplacian_spectrum(fnx_graph, weight="weight")
    elif impl == "nx":
        func = lambda: nx_laplacian_spectrum(nx_graph, weight="weight")
    else:
        raise ValueError(f"unknown spectrum impl: {impl}")

    values = func()
    checksum = float(np.asarray(values, dtype=np.float64)[0])
    start = time.perf_counter()
    for _ in range(loops):
        values = func()
        checksum += float(np.asarray(values, dtype=np.float64)[-1])
    elapsed = time.perf_counter() - start
    if not math.isfinite(checksum):
        raise AssertionError(checksum)
    return elapsed


def bench_spectrum(
    impl: str, n: int, loops: int, samples: int, output: Path | None
) -> dict[str, Any]:
    runs = [bench_spectrum_once(impl, n, loops) for _ in range(samples)]
    per_loop = [elapsed / loops for elapsed in runs]
    result = {
        "impl": impl,
        "loops": loops,
        "mean_per_loop_seconds": statistics.fmean(per_loop),
        "median_per_loop_seconds": statistics.median(per_loop),
        "n": n,
        "per_loop_seconds": per_loop,
        "samples": samples,
        "seconds": runs,
    }
    if output is not None:
        output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    return result


def _rounded_payload(values: Any) -> list[str]:
    rounded = []
    for value in values:
        number = float(value)
        if abs(number) < 5.0e-10:
            number = 0.0
        rounded.append(format(number, ".10f"))
    return rounded


def golden(sizes: list[int], output: Path | None) -> dict[str, Any]:
    raw_records = []
    raw_native_digest = []
    raw_numpy_digest = []
    max_abs_delta = 0.0
    max_rel_delta = 0.0
    for case in ("dense", "laplacian"):
        for n in sizes:
            matrix = matrix_for(case, n)
            payload = [float(value) for value in matrix.ravel(order="C")]
            ours = np.asarray(native_eigvals(payload, n), dtype=np.float64)
            expected = np.asarray(np.linalg.eigvalsh(matrix), dtype=np.float64)
            if ours.shape != expected.shape:
                raise AssertionError((case, n, ours.shape, expected.shape))
            deltas = np.abs(ours - expected)
            rels = deltas / np.maximum(np.abs(expected), 1.0)
            abs_delta = float(np.max(deltas)) if deltas.size else 0.0
            rel_delta = float(np.max(rels)) if rels.size else 0.0
            if not np.allclose(ours, expected, rtol=1.0e-10, atol=1.0e-10):
                raise AssertionError((case, n, abs_delta, rel_delta))
            max_abs_delta = max(max_abs_delta, abs_delta)
            max_rel_delta = max(max_rel_delta, rel_delta)
            raw_records.append(
                {
                    "case": case,
                    "max_abs_delta": abs_delta,
                    "max_rel_delta": rel_delta,
                    "n": n,
                    "native": _rounded_payload(ours),
                    "numpy": _rounded_payload(expected),
                }
            )
            raw_native_digest.append(
                {"case": case, "n": n, "values": _rounded_payload(ours)}
            )
            raw_numpy_digest.append(
                {"case": case, "n": n, "values": _rounded_payload(expected)}
            )

    encoded = json.dumps(raw_records, sort_keys=True, separators=(",", ":")).encode()
    native_encoded = json.dumps(
        raw_native_digest, sort_keys=True, separators=(",", ":")
    ).encode()
    numpy_encoded = json.dumps(
        raw_numpy_digest, sort_keys=True, separators=(",", ":")
    ).encode()
    native_sha = hashlib.sha256(native_encoded).hexdigest()
    numpy_sha = hashlib.sha256(numpy_encoded).hexdigest()
    result = {
        "bead": "br-r37-c1-04z53.9111",
        "max_abs_delta": max_abs_delta,
        "max_rel_delta": max_rel_delta,
        "native_quantized_sha256": native_sha,
        "numpy_quantized_sha256": numpy_sha,
        "quantized_match": hmac.compare_digest(native_sha, numpy_sha),
        "raw_records": raw_records,
        "sha256": hashlib.sha256(encoded).hexdigest(),
        "sizes": sizes,
    }
    if output is not None:
        output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    return result


def profile_raw(impl: str, case: str, n: int, loops: int, output: Path) -> dict[str, Any]:
    profiler = cProfile.Profile()
    profiler.enable()
    elapsed = bench_raw_once(impl, case, n, loops)
    profiler.disable()
    summary = io.StringIO()
    stats = pstats.Stats(profiler, stream=summary).strip_dirs().sort_stats("cumtime")
    stats.print_stats(40)
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

    raw_parser = sub.add_parser("raw")
    raw_parser.add_argument("--impl", choices=("native", "numpy"), required=True)
    raw_parser.add_argument("--case", choices=("dense", "laplacian"), default="dense")
    raw_parser.add_argument("--n", type=int, default=200)
    raw_parser.add_argument("--loops", type=int, default=3)
    raw_parser.add_argument("--samples", type=int, default=5)
    raw_parser.add_argument("--output", type=Path)

    spectrum_parser = sub.add_parser("spectrum")
    spectrum_parser.add_argument("--impl", choices=("fnx", "nx"), required=True)
    spectrum_parser.add_argument("--n", type=int, default=400)
    spectrum_parser.add_argument("--loops", type=int, default=1)
    spectrum_parser.add_argument("--samples", type=int, default=5)
    spectrum_parser.add_argument("--output", type=Path)

    golden_parser = sub.add_parser("golden")
    golden_parser.add_argument("--sizes", default="8,16,50,100,200")
    golden_parser.add_argument("--output", type=Path)

    profile_parser = sub.add_parser("profile-raw")
    profile_parser.add_argument("--impl", choices=("native", "numpy"), required=True)
    profile_parser.add_argument("--case", choices=("dense", "laplacian"), default="dense")
    profile_parser.add_argument("--n", type=int, default=200)
    profile_parser.add_argument("--loops", type=int, default=5)
    profile_parser.add_argument("--output", type=Path, required=True)

    args = parser.parse_args()
    if args.cmd == "raw":
        result = bench_raw(args.impl, args.case, args.n, args.loops, args.samples, args.output)
    elif args.cmd == "spectrum":
        result = bench_spectrum(args.impl, args.n, args.loops, args.samples, args.output)
    elif args.cmd == "golden":
        sizes = [int(value) for value in args.sizes.split(",") if value]
        result = golden(sizes, args.output)
    else:
        result = profile_raw(args.impl, args.case, args.n, args.loops, args.output)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
