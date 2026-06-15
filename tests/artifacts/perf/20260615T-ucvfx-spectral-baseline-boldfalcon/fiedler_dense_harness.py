#!/usr/bin/env python3
"""Profile/proof harness for br-r37-c1-ucvfx fiedler_vector residual."""

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


NODE_COUNT = 90
EDGE_PROBABILITY = 0.20
SEED = 42


def build_pair() -> tuple[Any, Any]:
    nx_graph = nx.gnp_random_graph(NODE_COUNT, EDGE_PROBABILITY, seed=SEED)
    if not nx.is_connected(nx_graph):
        raise RuntimeError("fixture must be connected")
    fnx_graph = fnx.Graph()
    fnx_graph.add_nodes_from(nx_graph.nodes())
    fnx_graph.add_edges_from(nx_graph.edges())
    return fnx_graph, nx_graph


def canon(vector: Any) -> np.ndarray:
    arr = np.asarray(vector, dtype=float)
    j = int(np.argmax(np.abs(arr)))
    return -arr if arr[j] < 0 else arr


def digest(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def run_case(mod: Any, graph: Any) -> np.ndarray:
    return canon(mod.fiedler_vector(graph))


def residual(graph: Any, vector: np.ndarray) -> float:
    lap = fnx.laplacian_matrix(graph).toarray()
    lam = fnx.algebraic_connectivity(graph)
    return float(np.linalg.norm(lap @ vector - lam * vector))


def cmd_golden(args: argparse.Namespace) -> int:
    fnx_graph, nx_graph = build_pair()
    fnx_vec = run_case(fnx, fnx_graph)
    nx_vec = run_case(nx, nx_graph)
    max_abs_diff = float(np.max(np.abs(fnx_vec - nx_vec)))
    fnx_residual = residual(fnx_graph, fnx_vec)
    payload = {
        "bead": "br-r37-c1-ucvfx",
        "fixture": {
            "nodes": NODE_COUNT,
            "edges": nx_graph.number_of_edges(),
            "p": EDGE_PROBABILITY,
            "seed": SEED,
        },
        "max_abs_diff_vs_nx": max_abs_diff,
        "fnx_residual": fnx_residual,
        "all_match": max_abs_diff <= args.atol and fnx_residual <= args.residual_tol,
        "fnx_rounded": [round(float(x), 10) for x in fnx_vec],
        "nx_rounded": [round(float(x), 10) for x in nx_vec],
        "obligations": {
            "ordering": "Vector follows graph node insertion order 0..n-1.",
            "tie_breaking": "Eigenvector sign canonicalized by largest-magnitude component.",
            "floating_point": "Compared against NetworkX with residual and max-abs tolerance.",
            "rng": "Deterministic gnp_random_graph seed.",
        },
    }
    payload["semantic_sha256"] = digest(
        {
            "fnx_rounded": payload["fnx_rounded"],
            "max_abs_diff_vs_nx": round(max_abs_diff, 12),
            "fnx_residual": round(fnx_residual, 12),
        }
    )
    args.output.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n")
    return 0 if payload["all_match"] else 1


def summarize(samples: list[float]) -> dict[str, Any]:
    return {
        "seconds": samples,
        "median": statistics.median(samples),
        "mean": statistics.fmean(samples),
    }


def cmd_bench(args: argparse.Namespace) -> int:
    fnx_graph, nx_graph = build_pair()
    rows = []
    for which, mod, graph in (("fnx", fnx, fnx_graph), ("nx", nx, nx_graph)):
        for _ in range(args.warmup):
            run_case(mod, graph)
        samples = []
        checksum = 0.0
        for _ in range(args.repeats):
            start = time.perf_counter()
            for _ in range(args.loops):
                checksum += float(np.sum(run_case(mod, graph)))
            samples.append(time.perf_counter() - start)
        row = summarize(samples)
        row.update(
            {
                "which": which,
                "loops": args.loops,
                "checksum": checksum,
                "per_loop_median_ms": row["median"] * 1000.0 / args.loops,
                "per_loop_mean_ms": row["mean"] * 1000.0 / args.loops,
            }
        )
        rows.append(row)
    args.output.write_text(json.dumps({"rows": rows}, sort_keys=True, indent=2) + "\n")
    return 0


def cmd_loop(args: argparse.Namespace) -> int:
    fnx_graph, nx_graph = build_pair()
    mod, graph = (fnx, fnx_graph) if args.which == "fnx" else (nx, nx_graph)
    for _ in range(args.warmup):
        run_case(mod, graph)
    checksum = 0.0
    for _ in range(args.loops):
        checksum += float(np.sum(run_case(mod, graph)))
    print(f"{checksum:.12f}")
    return 0


def cmd_profile(args: argparse.Namespace) -> int:
    fnx_graph, nx_graph = build_pair()
    mod, graph = (fnx, fnx_graph) if args.which == "fnx" else (nx, nx_graph)
    for _ in range(args.warmup):
        run_case(mod, graph)
    profiler = cProfile.Profile()
    profiler.enable()
    checksum = 0.0
    for _ in range(args.loops):
        checksum += float(np.sum(run_case(mod, graph)))
    profiler.disable()
    out = io.StringIO()
    print(
        f"bead=br-r37-c1-ucvfx which={args.which} loops={args.loops} "
        f"checksum={checksum:.12f}",
        file=out,
    )
    stats = pstats.Stats(profiler, stream=out)
    stats.sort_stats("cumtime").print_stats(args.limit)
    print("\n--- tottime ---", file=out)
    stats.sort_stats("tottime").print_stats(args.limit)
    args.output.write_text(out.getvalue())
    return 0


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_golden = sub.add_parser("golden")
    p_golden.add_argument("--output", type=Path, required=True)
    p_golden.add_argument("--atol", type=float, default=1e-5)
    p_golden.add_argument("--residual-tol", type=float, default=1e-5)

    p_bench = sub.add_parser("bench")
    p_bench.add_argument("--output", type=Path, required=True)
    p_bench.add_argument("--loops", type=int, default=3)
    p_bench.add_argument("--repeats", type=int, default=5)
    p_bench.add_argument("--warmup", type=int, default=1)

    p_loop = sub.add_parser("loop")
    p_loop.add_argument("--which", choices=["fnx", "nx"], required=True)
    p_loop.add_argument("--loops", type=int, default=3)
    p_loop.add_argument("--warmup", type=int, default=1)

    p_profile = sub.add_parser("profile")
    p_profile.add_argument("--which", choices=["fnx", "nx"], required=True)
    p_profile.add_argument("--loops", type=int, default=3)
    p_profile.add_argument("--warmup", type=int, default=1)
    p_profile.add_argument("--limit", type=int, default=40)
    p_profile.add_argument("--output", type=Path, required=True)

    args = parser.parse_args()
    raise SystemExit(globals()[f"cmd_{args.cmd}"](args))


if __name__ == "__main__":
    main()
