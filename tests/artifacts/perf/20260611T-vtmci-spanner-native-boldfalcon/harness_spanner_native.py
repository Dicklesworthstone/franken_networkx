"""Baseline/profile harness for br-r37-c1-vtmci native _raw_spanner.

This file is intentionally artifact-local. It does not patch production code.
Benchmarks use prebuilt graphs so timings cover spanner execution, not fixture
construction.
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
from typing import Any, Callable

import franken_networkx as fnx
import networkx as nx
import networkx.algorithms.sparsifiers as nx_sparsifiers


ARTIFACT_DIR = Path(__file__).resolve().parent


def git_sha() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=ARTIFACT_DIR.parents[3],
            text=True,
        ).strip()
    except Exception as exc:  # pragma: no cover - diagnostic metadata only
        return f"unavailable:{type(exc).__name__}:{exc}"


def env_metadata() -> dict[str, Any]:
    return {
        "git_sha": git_sha(),
        "python": sys.version,
        "platform": platform.platform(),
        "executable": sys.executable,
        "fnx_file": getattr(fnx, "__file__", None),
        "raw_extension_file": getattr(fnx._fnx, "__file__", None),
        "raw_binding_is_extension_spanner": fnx._raw_spanner is fnx._fnx.spanner,
        "networkx_version": getattr(nx, "__version__", None),
        "virtual_env": os.environ.get("VIRTUAL_ENV"),
    }


def canonical_edge(u: Any, v: Any) -> tuple[str, str]:
    left = repr(u)
    right = repr(v)
    return (left, right) if left <= right else (right, left)


def graph_digest(graph: Any, weight: str | None = None) -> str:
    nodes = sorted(repr(node) for node in graph.nodes())
    edges = []
    for u, v in graph.edges():
        left, right = canonical_edge(u, v)
        if weight is None:
            edges.append((left, right))
        else:
            edges.append((left, right, graph[u][v].get(weight)))
    payload = {"nodes": nodes, "edges": sorted(edges)}
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=repr)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def to_fnx_graph(graph: nx.Graph, weight: str | None = None) -> fnx.Graph:
    out = fnx.Graph()
    out.add_nodes_from(graph.nodes())
    if weight is None:
        out.add_edges_from(graph.edges())
    else:
        out.add_edges_from(
            (u, v, {weight: graph[u][v][weight]}) for u, v in graph.edges()
        )
    return out


def to_nx_graph(graph: Any, weight: str | None = None) -> nx.Graph:
    out = nx.Graph()
    out.add_nodes_from(graph.nodes())
    if weight is None:
        out.add_edges_from(graph.edges())
    else:
        out.add_edges_from(
            (u, v, {weight: graph[u][v][weight]}) for u, v in graph.edges()
        )
    return out


def assert_valid_spanner(
    original: nx.Graph,
    candidate: nx.Graph,
    stretch: float,
    weight: str | None = None,
) -> None:
    assert set(original.nodes()) == set(candidate.nodes()), "node set changed"
    assert not candidate.is_directed(), "candidate is directed"
    assert not candidate.is_multigraph(), "candidate is multigraph"
    for u, v in candidate.edges():
        assert original.has_edge(u, v), f"candidate has non-original edge {(u, v)!r}"
        if weight is not None:
            assert candidate[u][v][weight] == original[u][v][weight], (
                "candidate changed edge weight",
                u,
                v,
            )

    if weight is None:
        original_paths = dict(nx.all_pairs_shortest_path_length(original))
        candidate_paths = dict(nx.all_pairs_shortest_path_length(candidate))
    else:
        original_paths = dict(nx.all_pairs_dijkstra_path_length(original, weight=weight))
        candidate_paths = dict(nx.all_pairs_dijkstra_path_length(candidate, weight=weight))

    for source, distances in original_paths.items():
        candidate_distances = candidate_paths.get(source, {})
        for target, original_distance in distances.items():
            candidate_distance = candidate_distances.get(target, math.inf)
            assert candidate_distance <= stretch * original_distance + 1e-9, (
                "stretch violation",
                source,
                target,
                original_distance,
                candidate_distance,
                stretch,
            )


def make_case(
    name: str,
    *,
    n: int,
    p: float,
    graph_seed: int,
    stretch: float,
    spanner_seed: int,
    weight: str | None = None,
) -> dict[str, Any]:
    graph = nx.gnp_random_graph(n, p, seed=graph_seed)
    if weight is not None:
        for index, (u, v) in enumerate(sorted(graph.edges())):
            graph[u][v][weight] = 1 + ((index * 17 + graph_seed) % 23)
    return {
        "name": name,
        "n": n,
        "p": p,
        "graph_seed": graph_seed,
        "stretch": stretch,
        "spanner_seed": spanner_seed,
        "weight": weight,
        "nx_graph": graph,
        "fnx_graph": to_fnx_graph(graph, weight),
    }


def benchmark_cases() -> list[dict[str, Any]]:
    return [
        make_case(
            "unweighted_n400_p004_s3",
            n=400,
            p=0.04,
            graph_seed=7,
            stretch=3,
            spanner_seed=42,
        ),
        make_case(
            "unweighted_n800_p002_s3",
            n=800,
            p=0.02,
            graph_seed=7,
            stretch=3,
            spanner_seed=42,
        ),
        make_case(
            "unweighted_n1500_p001_s3",
            n=1500,
            p=0.01,
            graph_seed=7,
            stretch=3,
            spanner_seed=42,
        ),
        make_case(
            "weighted_n600_p0025_s4",
            n=600,
            p=0.025,
            graph_seed=11,
            stretch=4,
            spanner_seed=99,
            weight="weight",
        ),
    ]


def proof_cases() -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = [
        {
            "name": "path10_stretch1",
            "nx_graph": nx.path_graph(10),
            "stretch": 1,
            "spanner_seed": 3,
            "weight": None,
        },
        {
            "name": "cycle30_stretch3",
            "nx_graph": nx.cycle_graph(30),
            "stretch": 3,
            "spanner_seed": 5,
            "weight": None,
        },
        {
            "name": "complete20_stretch5",
            "nx_graph": nx.complete_graph(20),
            "stretch": 5,
            "spanner_seed": 7,
            "weight": None,
        },
    ]
    for seed in range(6):
        cases.append(
            {
                "name": f"gnp80_seed{seed}_stretch5",
                "nx_graph": nx.gnp_random_graph(80, 0.1, seed=seed),
                "stretch": 5,
                "spanner_seed": seed + 20,
                "weight": None,
            }
        )
    weighted = nx.gnp_random_graph(70, 0.12, seed=101)
    for index, (u, v) in enumerate(sorted(weighted.edges())):
        weighted[u][v]["weight"] = 1 + ((index * 13) % 19)
    cases.append(
        {
            "name": "weighted_gnp70_stretch4",
            "nx_graph": weighted,
            "stretch": 4,
            "spanner_seed": 31,
            "weight": "weight",
        }
    )
    for case in cases:
        case["fnx_graph"] = to_fnx_graph(case["nx_graph"], case["weight"])
    return cases


def time_call(fn: Callable[[], Any], runs: int, weight: str | None = None) -> dict[str, Any]:
    timings = []
    last_digest = None
    last_edges = None
    for _ in range(runs):
        start = time.perf_counter()
        result = fn()
        elapsed = time.perf_counter() - start
        timings.append(elapsed)
        last_digest = graph_digest(result, weight)
        last_edges = result.number_of_edges()
    timings_sorted = sorted(timings)
    return {
        "runs": runs,
        "best_ms": min(timings) * 1000,
        "median_ms": statistics.median(timings) * 1000,
        "mean_ms": statistics.mean(timings) * 1000,
        "p95_ms": timings_sorted[min(len(timings_sorted) - 1, int(len(timings_sorted) * 0.95))]
        * 1000,
        "last_edge_count": last_edges,
        "last_digest": last_digest,
    }


def run_one(path: str, case: dict[str, Any]) -> Any:
    stretch = case["stretch"]
    seed = case["spanner_seed"]
    weight = case["weight"]
    if path == "raw":
        return fnx._raw_spanner(case["fnx_graph"], stretch, weight=weight, seed=seed)
    if path == "public_fnx":
        return fnx.spanner(case["fnx_graph"], stretch, weight=weight, seed=seed)
    if path == "networkx":
        return nx_sparsifiers.spanner(case["nx_graph"], stretch, weight=weight, seed=seed)
    raise ValueError(f"unknown path: {path}")


def command_bench_one(args: argparse.Namespace) -> None:
    cases = {case["name"]: case for case in benchmark_cases()}
    case = cases[args.case]
    start = time.perf_counter()
    result = run_one(args.path, case)
    elapsed_ms = (time.perf_counter() - start) * 1000
    print(
        json.dumps(
            {
                "path": args.path,
                "case": args.case,
                "elapsed_ms": elapsed_ms,
                "edge_count": result.number_of_edges(),
                "digest": graph_digest(result, case["weight"]),
            },
            sort_keys=True,
        )
    )


def command_baseline(args: argparse.Namespace) -> None:
    rows = []
    for case in benchmark_cases():
        row = {
            key: case[key]
            for key in ("name", "n", "p", "graph_seed", "stretch", "spanner_seed", "weight")
        }
        row["input_edge_count"] = case["nx_graph"].number_of_edges()
        for path in ("raw", "public_fnx", "networkx"):
            run_one(path, case)
            row[path] = time_call(
                lambda path=path, case=case: run_one(path, case),
                args.runs,
                case["weight"],
            )
        row["ratios"] = {
            "raw_vs_networkx_median": row["networkx"]["median_ms"] / row["raw"]["median_ms"],
            "public_fnx_vs_networkx_median": row["networkx"]["median_ms"]
            / row["public_fnx"]["median_ms"],
            "raw_vs_public_fnx_median": row["public_fnx"]["median_ms"]
            / row["raw"]["median_ms"],
        }
        rows.append(row)
    output = {
        "metadata": env_metadata(),
        "benchmark_notes": {
            "timing_scope": "prebuilt graph objects; fixture construction excluded",
            "runs_per_path": args.runs,
            "paths": {
                "raw": "franken_networkx._raw_spanner / franken_networkx._fnx.spanner",
                "public_fnx": "franken_networkx.spanner, currently _spanner_inproc",
                "networkx": "networkx.algorithms.sparsifiers.spanner",
            },
        },
        "cases": rows,
    }
    args.output.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")
    print(json.dumps(output, indent=2, sort_keys=True))


def command_profile(args: argparse.Namespace) -> None:
    cases = {case["name"]: case for case in benchmark_cases()}
    case = cases[args.case]

    def target() -> None:
        for _ in range(args.loops):
            run_one("raw", case)

    profile = cProfile.Profile()
    profile.enable()
    target()
    profile.disable()
    stream = io.StringIO()
    stats = pstats.Stats(profile, stream=stream).strip_dirs().sort_stats("cumtime")
    stats.print_stats(args.limit)
    text = "\n".join(
        [
            "# cProfile raw native _raw_spanner",
            json.dumps(
                {
                    "metadata": env_metadata(),
                    "case": {
                        key: case[key]
                        for key in (
                            "name",
                            "n",
                            "p",
                            "graph_seed",
                            "stretch",
                            "spanner_seed",
                            "weight",
                        )
                    },
                    "loops": args.loops,
                    "profile_scope": "prebuilt fnx.Graph; repeated calls to fnx._raw_spanner",
                    "native_visibility_note": (
                        "cProfile attributes Rust-side work to the PyO3 built-in "
                        "franken_networkx._fnx.spanner frame."
                    ),
                },
                indent=2,
                sort_keys=True,
            ),
            "",
            stream.getvalue(),
        ]
    )
    args.output.write_text(text)
    print(text)


def command_workload(args: argparse.Namespace) -> None:
    cases = {case["name"]: case for case in benchmark_cases()}
    case = cases[args.case]
    result = None
    for _ in range(args.loops):
        result = run_one(args.path, case)
    assert result is not None
    print(
        json.dumps(
            {
                "path": args.path,
                "case": args.case,
                "loops": args.loops,
                "edge_count": result.number_of_edges(),
                "digest": graph_digest(result, case["weight"]),
            },
            sort_keys=True,
        )
    )


def command_proof(args: argparse.Namespace) -> None:
    results = []
    failures = []
    for case in proof_cases():
        raw = run_one("raw", case)
        raw_nx = to_nx_graph(raw, case["weight"])
        public = run_one("public_fnx", case)
        nx_result = run_one("networkx", case)
        try:
            assert_valid_spanner(case["nx_graph"], raw_nx, case["stretch"], case["weight"])
            status = "pass"
        except AssertionError as exc:
            status = "fail"
            failures.append({"case": case["name"], "error": repr(exc)})
        results.append(
            {
                "name": case["name"],
                "status": status,
                "node_count": case["nx_graph"].number_of_nodes(),
                "input_edge_count": case["nx_graph"].number_of_edges(),
                "raw_edge_count": raw.number_of_edges(),
                "public_fnx_edge_count": public.number_of_edges(),
                "networkx_edge_count": nx_result.number_of_edges(),
                "stretch": case["stretch"],
                "weight": case["weight"],
                "spanner_seed": case["spanner_seed"],
                "input_digest": graph_digest(case["nx_graph"], case["weight"]),
                "raw_digest": graph_digest(raw, case["weight"]),
                "public_fnx_digest": graph_digest(public, case["weight"]),
                "networkx_digest": graph_digest(nx_result, case["weight"]),
            }
        )

    output = {
        "metadata": env_metadata(),
        "proof_status": "pass" if not failures else "fail",
        "checks_passed": len(results) - len(failures),
        "checks_total": len(results),
        "failures": failures,
        "contracts": {
            "exact_edge_identity_required": False,
            "structural_contract": [
                "raw output node set equals input node set",
                "raw output is an undirected simple graph",
                "every raw output edge exists in the input graph",
                "weighted raw output preserves requested edge weight attribute",
                "all-pairs distances satisfy candidate_distance <= stretch * original_distance",
            ],
            "ordering_tie_rng_notes": [
                "Baswana-Sen spanner is randomized; exact edge identity is not part of the public contract.",
                "Raw Rust kernel uses its deterministic Rust RNG path for the supplied integer seed.",
                "NetworkX tie behavior depends on Python object identity and container iteration; proof records digests but accepts any valid spanner.",
                "All proof cases supply deterministic graph seeds and spanner seeds.",
            ],
        },
        "results": results,
    }
    args.output.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")
    print(json.dumps(output, indent=2, sort_keys=True))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    bench_one = subparsers.add_parser("bench-one")
    bench_one.add_argument("--path", choices=["raw", "public_fnx", "networkx"], required=True)
    bench_one.add_argument("--case", default="unweighted_n800_p002_s3")
    bench_one.set_defaults(func=command_bench_one)

    baseline = subparsers.add_parser("baseline")
    baseline.add_argument("--runs", type=int, default=7)
    baseline.add_argument("--output", type=Path, default=ARTIFACT_DIR / "baseline_direct.json")
    baseline.set_defaults(func=command_baseline)

    profile = subparsers.add_parser("profile")
    profile.add_argument("--case", default="unweighted_n800_p002_s3")
    profile.add_argument("--loops", type=int, default=20)
    profile.add_argument("--limit", type=int, default=35)
    profile.add_argument("--output", type=Path, default=ARTIFACT_DIR / "baseline_profile_raw.txt")
    profile.set_defaults(func=command_profile)

    workload = subparsers.add_parser("workload")
    workload.add_argument("--path", choices=["raw", "public_fnx", "networkx"], required=True)
    workload.add_argument("--case", default="unweighted_n800_p002_s3")
    workload.add_argument("--loops", type=int, default=200)
    workload.set_defaults(func=command_workload)

    proof = subparsers.add_parser("proof")
    proof.add_argument("--output", type=Path, default=ARTIFACT_DIR / "baseline_proof.json")
    proof.set_defaults(func=command_proof)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
