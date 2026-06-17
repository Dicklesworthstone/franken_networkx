#!/usr/bin/env python3
"""Measurement harness for br-r37-c1-04z53.9133.

Captures pre-edit timing, profile, and sorted-value parity for:
    fnx.laplacian_spectrum(fnx.star_graph(798))
"""

from __future__ import annotations

import argparse
import cProfile
import hashlib
import io
import json
import math
import os
import platform
import pstats
import statistics
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import networkx as nx
import numpy as np

import franken_networkx as fnx


SPOKES = 798
NODES = SPOKES + 1

nx_laplacian_spectrum = getattr(
    nx.laplacian_spectrum, "orig_func", nx.laplacian_spectrum
)


def fnx_once() -> np.ndarray:
    return np.asarray(fnx.laplacian_spectrum(fnx.star_graph(SPOKES)), dtype=np.float64)


def nx_once() -> np.ndarray:
    return np.asarray(
        nx_laplacian_spectrum(nx.star_graph(SPOKES)), dtype=np.float64
    )


def expected_sorted() -> np.ndarray:
    values = np.ones(NODES, dtype=np.float64)
    values[0] = 0.0
    values[-1] = float(NODES)
    return values


def q9_sorted_payload(values: np.ndarray) -> list[str]:
    sorted_values = np.sort(np.asarray(values, dtype=np.float64))
    payload = []
    for value in sorted_values:
        number = float(value)
        if math.isclose(number, 0.0, abs_tol=5.0e-10):
            number = 0.0
        payload.append(f"{number:.9f}")
    return payload


def sha256_json(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def env_record() -> dict[str, Any]:
    return {
        "cwd": os.getcwd(),
        "fnx_file": getattr(fnx, "__file__", None),
        "fnx_version": getattr(fnx, "__version__", "unknown"),
        "git_head": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True
        ).strip(),
        "networkx_file": getattr(nx, "__file__", None),
        "networkx_version": nx.__version__,
        "numpy_version": np.__version__,
        "thread_env": {
            "MKL_NUM_THREADS": os.environ.get("MKL_NUM_THREADS"),
            "NUMEXPR_NUM_THREADS": os.environ.get("NUMEXPR_NUM_THREADS"),
            "OMP_NUM_THREADS": os.environ.get("OMP_NUM_THREADS"),
            "OPENBLAS_NUM_THREADS": os.environ.get("OPENBLAS_NUM_THREADS"),
        },
        "platform": platform.platform(),
        "python": sys.version,
        "target_expression": "fnx.laplacian_spectrum(fnx.star_graph(798))",
    }


def parity(output: Path) -> dict[str, Any]:
    fnx_values = fnx_once()
    nx_values = nx_once()
    expected = expected_sorted()

    fnx_sorted = np.sort(fnx_values)
    nx_sorted = np.sort(nx_values)
    expected_delta = np.abs(fnx_sorted - expected)
    nx_delta = np.abs(fnx_sorted - nx_sorted)

    contract = {
        "expression": "fnx.laplacian_spectrum(fnx.star_graph(798))",
        "n_nodes": NODES,
        "n_spokes": SPOKES,
        "expected_multiplicities": {
            "0.0": 1,
            "1.0": NODES - 2,
            "799.0": 1,
        },
        "fnx_dtype": str(fnx_values.dtype),
        "networkx_dtype": str(nx_values.dtype),
        "fnx_shape": list(fnx_values.shape),
        "networkx_shape": list(nx_values.shape),
        "sorted_value_order": "ascending",
        "fnx_first5_sorted": [float(x) for x in fnx_sorted[:5]],
        "fnx_last5_sorted": [float(x) for x in fnx_sorted[-5:]],
        "networkx_first5_sorted": [float(x) for x in nx_sorted[:5]],
        "networkx_last5_sorted": [float(x) for x in nx_sorted[-5:]],
        "max_sorted_delta_fnx_vs_networkx": float(nx_delta.max()),
        "max_sorted_delta_fnx_vs_closed_form": float(expected_delta.max()),
        "allclose_fnx_networkx_1e_8": bool(
            np.allclose(fnx_sorted, nx_sorted, rtol=1.0e-8, atol=1.0e-8)
        ),
        "allclose_fnx_closed_form_1e_8": bool(
            np.allclose(fnx_sorted, expected, rtol=1.0e-8, atol=1.0e-8)
        ),
    }
    q9_payload = {
        "dtype": "float64",
        "n_nodes": NODES,
        "sorted_values_q9": q9_sorted_payload(fnx_values),
    }
    contract["q9_sorted_sha256"] = sha256_json(q9_payload)
    contract["q9_sorted_payload_file"] = "q9_sorted_payload.json"

    output.mkdir(parents=True, exist_ok=True)
    (output / "parity_contract.json").write_text(
        json.dumps(contract, indent=2, sort_keys=True) + "\n"
    )
    (output / "q9_sorted_payload.json").write_text(
        json.dumps(q9_payload, indent=2, sort_keys=True) + "\n"
    )
    return contract


def direct_timing(output: Path, samples: int, warmups: int) -> dict[str, Any]:
    def run(label: str, func: Any) -> dict[str, Any]:
        for _ in range(warmups):
            func()
        times = []
        for _ in range(samples):
            start = time.perf_counter()
            values = func()
            elapsed = time.perf_counter() - start
            times.append(elapsed)
            if values.shape != (NODES,):
                raise AssertionError((label, values.shape))
        sorted_times = sorted(times)
        return {
            "samples": samples,
            "seconds": times,
            "min_seconds": min(times),
            "median_seconds": statistics.median(times),
            "mean_seconds": statistics.fmean(times),
            "p95_seconds": sorted_times[min(len(sorted_times) - 1, int(0.95 * samples))],
            "p99_seconds": sorted_times[min(len(sorted_times) - 1, int(0.99 * samples))],
            "warmups": warmups,
        }

    result = {
        "expression_includes_graph_construction": True,
        "fnx": run("fnx", fnx_once),
        "networkx": run("networkx", nx_once),
    }
    result["fnx_vs_networkx_median_ratio"] = (
        result["fnx"]["median_seconds"] / result["networkx"]["median_seconds"]
    )
    output.mkdir(parents=True, exist_ok=True)
    (output / "direct_timing.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n"
    )
    return result


def profile_fnx(output: Path, loops: int) -> dict[str, Any]:
    profiler = cProfile.Profile()
    profiler.enable()
    start = time.perf_counter()
    for _ in range(loops):
        values = fnx_once()
        if values.shape != (NODES,):
            raise AssertionError(values.shape)
    elapsed = time.perf_counter() - start
    profiler.disable()

    summary = io.StringIO()
    stats = pstats.Stats(profiler, stream=summary).strip_dirs().sort_stats("cumtime")
    stats.print_stats(40)
    output.mkdir(parents=True, exist_ok=True)
    (output / "cprofile_fnx_top.txt").write_text(summary.getvalue())
    result = {
        "elapsed_seconds": elapsed,
        "loops": loops,
        "profile_file": "cprofile_fnx_top.txt",
        "seconds_per_call": elapsed / loops,
        "sort": "cumtime",
    }
    (output / "profile_summary.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n"
    )
    return result


def bench_once(impl: str, loops: int) -> None:
    func = fnx_once if impl == "fnx" else nx_once
    for _ in range(loops):
        values = func()
        if values.shape != (NODES,):
            raise AssertionError(values.shape)


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)

    all_parser = sub.add_parser("all")
    all_parser.add_argument("--output", type=Path, required=True)
    all_parser.add_argument("--samples", type=int, default=11)
    all_parser.add_argument("--profile-loops", type=int, default=5)
    all_parser.add_argument("--warmups", type=int, default=3)

    bench_parser = sub.add_parser("bench-once")
    bench_parser.add_argument("--impl", choices=("fnx", "networkx"), required=True)
    bench_parser.add_argument("--loops", type=int, default=5)

    args = parser.parse_args()
    if args.cmd == "bench-once":
        bench_once(args.impl, args.loops)
        return

    args.output.mkdir(parents=True, exist_ok=True)
    env = env_record()
    (args.output / "environment.json").write_text(
        json.dumps(env, indent=2, sort_keys=True) + "\n"
    )
    result = {
        "environment": env,
        "parity": parity(args.output),
        "direct_timing": direct_timing(args.output, args.samples, args.warmups),
        "profile": profile_fnx(args.output, args.profile_loops),
    }
    (args.output / "measurement_summary.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n"
    )
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
