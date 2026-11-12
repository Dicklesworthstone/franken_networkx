#!/usr/bin/env python3
"""Benchmark and golden-output proof for br-r37-c1-u5uob."""

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
import networkx.algorithms.bipartite as nx_bp

import franken_networkx as fnx
import franken_networkx.bipartite as fnx_bp


def _add_fixture_edges(graph: Any, half: int, weighted: bool) -> None:
    for u in range(half):
        v0 = half + u
        v1 = half + ((u + 1) % half)
        if weighted:
            graph.add_edge(u, v0, weight=1.0 + ((u * 7) % 13) / 10.0)
            graph.add_edge(u, v1, weight=1.0 + ((u * 11) % 17) / 10.0)
        else:
            graph.add_edge(u, v0)
            graph.add_edge(u, v1)

    for u in range(half):
        for step in (3, 9, 17):
            if (u * 37 + step) % 5 == 0:
                continue
            v = half + ((u * step + 7) % half)
            if weighted:
                graph.add_edge(u, v, weight=0.5 + ((u + step * 3) % 19) / 7.0)
            else:
                graph.add_edge(u, v)


def make_pair(half: int, weighted: bool) -> tuple[Any, Any]:
    fg = fnx.Graph()
    ng = nx.Graph()
    for graph in (fg, ng):
        for i in range(half):
            graph.add_node(i, bipartite=0)
        for i in range(half, half * 2):
            graph.add_node(i, bipartite=1)
        _add_fixture_edges(graph, half, weighted)
    return fg, ng


def _float_payload(value: Any) -> Any:
    if isinstance(value, dict):
        return [[repr(k), _float_payload(v)] for k, v in sorted(value.items(), key=lambda item: repr(item[0]))]
    if isinstance(value, (list, tuple)):
        return [_float_payload(v) for v in value]
    if isinstance(value, float):
        if math.isnan(value):
            return "NaN"
        if math.isinf(value):
            return "Infinity" if value > 0 else "-Infinity"
        return format(value, ".17g")
    return value


def semantics(half: int, weighted: bool) -> dict[str, Any]:
    fg, ng = make_pair(half, weighted)
    nodes = list(range(0, half * 2, max(1, half // 12)))
    fnx_scalar = fnx_bp.spectral_bipartivity(fg, weight="weight")
    nx_scalar = nx_bp.spectral_bipartivity(ng, weight="weight")
    fnx_nodes = fnx_bp.spectral_bipartivity(fg, nodes=nodes, weight="weight")
    nx_nodes = nx_bp.spectral_bipartivity(ng, nodes=nodes, weight="weight")
    scalar_delta = abs(float(fnx_scalar) - float(nx_scalar))
    node_delta = max(abs(float(fnx_nodes[n]) - float(nx_nodes[n])) for n in nodes)
    return {
        "case": {"half": half, "weighted": weighted, "nodes": nodes},
        "fnx_scalar": _float_payload(fnx_scalar),
        "nx_scalar": _float_payload(nx_scalar),
        "fnx_nodes": _float_payload(fnx_nodes),
        "nx_nodes": _float_payload(nx_nodes),
        "max_abs_delta": max(scalar_delta, node_delta),
    }


def golden(half: int, weighted: bool, output: Path | None) -> dict[str, Any]:
    payload = semantics(half, weighted)
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    result = {
        "sha256": hashlib.sha256(encoded).hexdigest(),
        "payload": payload,
    }
    if output is not None:
        output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    return result


def bench_once(half: int, weighted: bool, mode: str, loops: int) -> float:
    graph, _ = make_pair(half, weighted)
    nodes = list(range(0, half * 2, max(1, half // 12)))
    fnx_bp.spectral_bipartivity(graph, weight="weight")
    if mode == "nodes":
        fnx_bp.spectral_bipartivity(graph, nodes=nodes, weight="weight")

    start = time.perf_counter()
    for _ in range(loops):
        if mode == "scalar":
            fnx_bp.spectral_bipartivity(graph, weight="weight")
        elif mode == "nodes":
            fnx_bp.spectral_bipartivity(graph, nodes=nodes, weight="weight")
        else:
            fnx_bp.spectral_bipartivity(graph, weight="weight")
            fnx_bp.spectral_bipartivity(graph, nodes=nodes, weight="weight")
    return time.perf_counter() - start


def bench(half: int, weighted: bool, mode: str, loops: int, samples: int, output: Path | None) -> dict[str, Any]:
    runs = [bench_once(half, weighted, mode, loops) for _ in range(samples)]
    per_call = [elapsed / loops for elapsed in runs]
    result = {
        "case": {"half": half, "nodes": half * 2, "weighted": weighted, "mode": mode},
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


def profile(half: int, weighted: bool, mode: str, loops: int, output: Path) -> dict[str, Any]:
    profiler = cProfile.Profile()
    profiler.enable()
    elapsed = bench_once(half, weighted, mode, loops)
    profiler.disable()

    summary = io.StringIO()
    stats = pstats.Stats(profiler, stream=summary).strip_dirs().sort_stats("cumtime")
    stats.print_stats(35)
    output.write_text(summary.getvalue())
    return {
        "case": {"half": half, "nodes": half * 2, "weighted": weighted, "mode": mode},
        "loops": loops,
        "elapsed_seconds": elapsed,
        "profile": str(output),
    }


def compare(half: int, weighted: bool, tolerance: float) -> dict[str, Any]:
    result = semantics(half, weighted)
    if float(result["max_abs_delta"]) > tolerance:
        raise SystemExit(
            f"max_abs_delta {result['max_abs_delta']:.3e} exceeds tolerance {tolerance:.3e}"
        )
    return {"ok": True, "tolerance": tolerance, **result}


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)

    for name in ("bench", "profile", "golden", "compare"):
        p = sub.add_parser(name)
        p.add_argument("--half", type=int, default=96)
        p.add_argument("--weighted", action="store_true")
        if name in {"bench", "profile"}:
            p.add_argument("--mode", choices=("scalar", "nodes", "both"), default="both")
            p.add_argument("--loops", type=int, default=8)
        if name == "bench":
            p.add_argument("--samples", type=int, default=7)
            p.add_argument("--output", type=Path)
        elif name == "profile":
            p.add_argument("--output", type=Path, required=True)
        elif name == "golden":
            p.add_argument("--output", type=Path)
        else:
            p.add_argument("--tolerance", type=float, default=1e-10)

    args = parser.parse_args()
    if args.cmd == "bench":
        result = bench(args.half, args.weighted, args.mode, args.loops, args.samples, args.output)
    elif args.cmd == "profile":
        result = profile(args.half, args.weighted, args.mode, args.loops, args.output)
    elif args.cmd == "golden":
        result = golden(args.half, args.weighted, args.output)
    else:
        result = compare(args.half, args.weighted, args.tolerance)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
