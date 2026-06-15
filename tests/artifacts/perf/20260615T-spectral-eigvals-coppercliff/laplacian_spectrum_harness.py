#!/usr/bin/env python3
"""Benchmark/golden harness for br-r37-c1-04z53.9109."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import time

import franken_networkx as fnx
import networkx as nx
import numpy as np


def build_graph(module, case: str):
    if case == "path8":
        return module.path_graph(8)
    if case == "cycle10":
        return module.cycle_graph(10)
    if case == "star16":
        return module.star_graph(15)
    if case == "complete20":
        return module.complete_graph(20)
    if case == "grid25":
        return module.grid_2d_graph(5, 5)
    if case == "path32":
        return module.path_graph(32)
    if case == "selfloop2":
        graph = module.Graph()
        graph.add_nodes_from([0, 1])
        graph.add_edge(0, 0)
        graph.add_edge(0, 1)
        return graph
    if case == "weighted_fallback":
        graph = module.path_graph(8)
        graph[0][1]["weight"] = 3.5
        return graph
    raise ValueError(f"unknown case {case!r}")


def configure_mode(mode: str) -> None:
    if mode == "fallback":
        fnx._LAPLACIAN_SPECTRUM_NATIVE_MAX_N = 0
        fnx._LAPLACIAN_SPECTRUM_NATIVE_EIG_MAX_N = 0
    elif mode == "native":
        pass
    elif mode == "networkx":
        pass
    else:
        raise ValueError(f"unknown mode {mode!r}")


def spectrum(mode: str, case: str):
    if mode == "networkx":
        return np.asarray(nx.laplacian_spectrum(build_graph(nx, case)), dtype=np.float64)
    configure_mode(mode)
    return np.asarray(fnx.laplacian_spectrum(build_graph(fnx, case)), dtype=np.float64)


def bench(mode: str, case: str, loops: int) -> dict[str, float | str | int]:
    configure_mode(mode)
    graph = build_graph(nx if mode == "networkx" else fnx, case)
    func = nx.laplacian_spectrum if mode == "networkx" else fnx.laplacian_spectrum
    checksum = 0.0
    start = time.perf_counter()
    for _ in range(loops):
        values = np.asarray(func(graph), dtype=np.float64)
        checksum += float(values[0]) + float(values[-1])
    elapsed = time.perf_counter() - start
    print(f"{mode} {case} loops={loops} elapsed={elapsed:.12f} checksum={checksum:.12f}")
    return {
        "mode": mode,
        "case": case,
        "loops": loops,
        "elapsed_seconds": elapsed,
        "seconds_per_loop": elapsed / loops,
        "checksum": checksum,
    }


def golden(cases: list[str]) -> dict[str, object]:
    records = []
    max_abs = 0.0
    max_rel = 0.0
    for case in cases:
        ours = spectrum("native", case)
        expected = spectrum("networkx", case)
        if ours.shape != expected.shape:
            raise AssertionError((case, ours.shape, expected.shape))
        abs_delta = float(np.max(np.abs(ours - expected))) if ours.size else 0.0
        denom = np.maximum(np.abs(expected), 1.0)
        rel_delta = float(np.max(np.abs(ours - expected) / denom)) if ours.size else 0.0
        if not np.allclose(ours, expected, rtol=1.0e-10, atol=1.0e-10):
            raise AssertionError((case, abs_delta, rel_delta, ours.tolist(), expected.tolist()))
        max_abs = max(max_abs, abs_delta)
        max_rel = max(max_rel, rel_delta)
        records.append(
            {
                "case": case,
                "n": int(ours.size),
                "ours_rounded": [round(float(x), 12) for x in ours],
                "expected_rounded": [round(float(x), 12) for x in expected],
                "max_abs_delta": abs_delta,
                "max_rel_delta": rel_delta,
            }
        )
    payload = {
        "bead": "br-r37-c1-04z53.9109",
        "cases": records,
        "max_abs_delta": max_abs,
        "max_rel_delta": max_rel,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    payload["sha256"] = hashlib.sha256(encoded).hexdigest()
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["native", "fallback", "networkx", "golden"], required=True)
    parser.add_argument("--case", default="path32")
    parser.add_argument("--loops", type=int, default=1000)
    parser.add_argument("--cases", nargs="*", default=["path8", "cycle10", "star16", "complete20", "grid25", "path32", "selfloop2", "weighted_fallback"])
    args = parser.parse_args()

    if args.mode == "golden":
        print(json.dumps(golden(args.cases), indent=2, sort_keys=True))
        return
    result = bench(args.mode, args.case, args.loops)
    if not math.isfinite(result["checksum"]):
        raise AssertionError(result)


if __name__ == "__main__":
    main()
