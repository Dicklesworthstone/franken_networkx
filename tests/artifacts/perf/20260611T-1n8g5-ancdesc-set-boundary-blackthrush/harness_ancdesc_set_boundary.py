#!/usr/bin/env python3
"""Proof and timing harness for br-r37-c1-1n8g5."""

from __future__ import annotations

import argparse
import cProfile
import hashlib
import hmac
import io
import json
import pstats
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[3]
sys.path.insert(0, str(REPO / "python"))

import franken_networkx as fnx
import networkx as nx


def _build_dag(module, n: int):
    graph = module.DiGraph()
    graph.add_nodes_from(range(n))
    graph.add_edges_from(
        (u, v)
        for u in range(n)
        for v in range(u + 1, min(n, u + 9))
        if (u * 17 + v) % 5 != 0
    )
    return graph


def _build_hash_equal_digraph(module):
    graph = module.DiGraph()
    graph.add_edge("s", 1.0)
    graph.add_edge(1, "t")
    graph.add_edge("r", False)
    graph.add_edge(0, "zero")
    return graph


def _build_undirected(module):
    graph = module.Graph()
    graph.add_edges_from([(0, 1), (1, 2), (2, 3), (10, 11)])
    return graph


def _build_multidigraph(module):
    graph = module.MultiDiGraph()
    graph.add_edge("a", "b", key="first")
    graph.add_edge("a", "b", key="second")
    graph.add_edge("b", "c", key="third")
    return graph


def _set_signature(value):
    if type(value) is not set:
        raise AssertionError(f"expected exact set, got {type(value)!r}")
    return sorted(f"{type(item).__name__}:{repr(item)}" for item in value)


def _digest(value) -> str:
    payload = json.dumps(value, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()


def _proof_cases(module, n: int):
    dag = _build_dag(module, n)
    hash_equal = _build_hash_equal_digraph(module)
    undirected = _build_undirected(module)
    multidigraph = _build_multidigraph(module)
    return {
        "descendants_dag": _set_signature(module.descendants(dag, 0)),
        "ancestors_dag": _set_signature(module.ancestors(dag, n - 1)),
        "descendants_hash_equal": _set_signature(module.descendants(hash_equal, "s")),
        "ancestors_hash_equal": _set_signature(module.ancestors(hash_equal, "zero")),
        "descendants_undirected": _set_signature(module.descendants(undirected, 0)),
        "ancestors_undirected": _set_signature(module.ancestors(undirected, 3)),
        "descendants_multidigraph": _set_signature(module.descendants(multidigraph, "a")),
        "ancestors_multidigraph": _set_signature(module.ancestors(multidigraph, "c")),
    }


def proof(label: str, n: int, compare: Path | None) -> None:
    previous = None
    if compare is not None:
        previous = json.loads(compare.read_text(encoding="utf-8"))
    fnx_cases = _proof_cases(fnx, n)
    nx_cases = _proof_cases(nx, n)
    if fnx_cases != nx_cases:
        raise AssertionError("FrankenNetworkX output signature differs from NetworkX")

    out = {
        "label": label,
        "n": n,
        "cases": {
            name: {
                "fnx_sha256": _digest(signature),
                "nx_sha256": _digest(nx_cases[name]),
                "fnx_matches_nx": True,
            }
            for name, signature in fnx_cases.items()
        },
        "suite_sha256": _digest(fnx_cases),
    }
    if previous is not None:
        baseline_sha = previous["suite_sha256"]
        out["baseline_suite_sha256"] = baseline_sha
        out["baseline_suite_sha256_equal"] = hmac.compare_digest(
            out["suite_sha256"], baseline_sha
        )
        if not out["baseline_suite_sha256_equal"]:
            raise AssertionError("golden suite sha changed")

    proof_path = ROOT / f"{label}_proof.json"
    proof_path.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")
    (ROOT / f"{label}_proof.sha256").write_text(
        hashlib.sha256(proof_path.read_bytes()).hexdigest() + "\n"
    )


def _time_repeated(func, reps: int) -> float:
    start = time.perf_counter()
    for _ in range(reps):
        func()
    return time.perf_counter() - start


def bench(label: str, n: int, samples: int, reps: int) -> None:
    dag_f = _build_dag(fnx, n)
    dag_n = _build_dag(nx, n)
    cases = (
        ("descendants_dag", lambda: fnx.descendants(dag_f, 0), lambda: nx.descendants(dag_n, 0)),
        ("ancestors_dag", lambda: fnx.ancestors(dag_f, n - 1), lambda: nx.ancestors(dag_n, n - 1)),
    )
    out = {"label": label, "n": n, "samples": samples, "reps_per_sample": reps, "cases": {}}
    for name, fnx_fn, nx_fn in cases:
        case_out = {}
        for lib_name, func in (("fnx", fnx_fn), ("nx", nx_fn)):
            values = [_time_repeated(func, reps) for _ in range(samples)]
            case_out[lib_name] = {
                "best_total": min(values),
                "median_total": statistics.median(values),
                "best_per_call": min(values) / reps,
                "median_per_call": statistics.median(values) / reps,
                "samples": values,
            }
        case_out["fnx_vs_nx_best_ratio"] = (
            case_out["fnx"]["best_per_call"] / case_out["nx"]["best_per_call"]
        )
        case_out["fnx_vs_nx_median_ratio"] = (
            case_out["fnx"]["median_per_call"] / case_out["nx"]["median_per_call"]
        )
        out["cases"][name] = case_out
    (ROOT / f"{label}_bench.json").write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")


def profile(label: str, n: int, reps: int) -> None:
    dag = _build_dag(fnx, n)

    def run():
        for _ in range(reps):
            fnx.descendants(dag, 0)
            fnx.ancestors(dag, n - 1)

    profiler = cProfile.Profile()
    profiler.enable()
    run()
    profiler.disable()
    stream = io.StringIO()
    pstats.Stats(profiler, stream=stream).strip_dirs().sort_stats("cumtime").print_stats(80)
    (ROOT / f"{label}_profile.txt").write_text(stream.getvalue())


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["proof", "bench", "profile"])
    parser.add_argument("--label", required=True)
    parser.add_argument("--n", type=int, default=450)
    parser.add_argument("--samples", type=int, default=13)
    parser.add_argument("--reps", type=int, default=400)
    parser.add_argument("--compare", type=Path)
    args = parser.parse_args()
    if args.command == "proof":
        proof(args.label, args.n, args.compare)
    elif args.command == "bench":
        bench(args.label, args.n, args.samples, args.reps)
    else:
        profile(args.label, args.n, args.reps)


if __name__ == "__main__":
    main()
