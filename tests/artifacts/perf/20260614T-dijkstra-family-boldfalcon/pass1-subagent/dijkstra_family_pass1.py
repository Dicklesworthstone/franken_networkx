#!/usr/bin/env python3
"""Pass 1 baseline/profile/golden for br-r37-c1-efv3d.

This is a measurement artifact only. It intentionally lives under
tests/artifacts/perf/... and does not modify source files.
"""

from __future__ import annotations

import argparse
import cProfile
import gc
import hashlib
import io
import json
import math
import os
import platform
import random
import statistics
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Callable

import franken_networkx as fnx
import networkx as nx
import pstats


SEED = 20260614
DEFAULT_NODES = 700
DEFAULT_EXTRA_EDGES = 3200
SOURCE = 0
WEIGHT = "weight"


def canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha256_obj(obj: Any) -> str:
    return hashlib.sha256(canonical_json(obj).encode("utf-8")).hexdigest()


def git_output(args: list[str]) -> str | None:
    try:
        return subprocess.check_output(args, text=True).strip()
    except Exception:
        return None


def make_edges(n: int, extra_edges: int, seed: int) -> list[tuple[int, int, Any]]:
    rng = random.Random(seed)
    edges: list[tuple[int, int, Any]] = []
    seen: set[tuple[int, int]] = set()

    def add(u: int, v: int, w: Any) -> None:
        if u == v:
            return
        a, b = (u, v) if u < v else (v, u)
        if (a, b) in seen:
            return
        seen.add((a, b))
        edges.append((u, v, w))

    for i in range(n - 1):
        add(i, i + 1, 1 + ((i * 17) % 13))
    while len(edges) < n - 1 + extra_edges:
        u = rng.randrange(n)
        v = rng.randrange(n)
        w = 1 + rng.randrange(37)
        add(u, v, w)
    return edges


def build_graph(mod: Any, edges: list[tuple[int, int, Any]], n: int) -> Any:
    graph = mod.Graph()
    graph.add_nodes_from(range(n))
    for u, v, w in edges:
        graph.add_edge(u, v, **{WEIGHT: w})
    return graph


def make_perf_pair(n: int, extra_edges: int, seed: int) -> tuple[Any, Any, list[tuple[int, int, Any]]]:
    edges = make_edges(n, extra_edges, seed)
    return build_graph(fnx, edges, n), build_graph(nx, edges, n), edges


def make_tie_edges() -> list[tuple[str, str, Any]]:
    return [
        ("s", "a", 1),
        ("s", "b", 1),
        ("a", "t", 2),
        ("b", "t", 2),
        ("a", "c", 1),
        ("b", "c", 1),
        ("c", "u", 1.5),
    ]


def make_disconnected_edges() -> list[tuple[str, str, Any]]:
    return [("a", "b", 1), ("c", "d", 1)]


def build_from_edges(mod: Any, edges: list[tuple[Any, Any, Any]]) -> Any:
    graph = mod.Graph()
    for u, v, w in edges:
        graph.add_edge(u, v, **{WEIGHT: w})
    return graph


def number_record(value: Any) -> dict[str, Any]:
    if isinstance(value, bool):
        return {"type": "bool", "value": value}
    if isinstance(value, int):
        return {"type": "int", "value": value}
    if isinstance(value, float):
        if math.isnan(value):
            encoded = "nan"
        elif math.isinf(value):
            encoded = "inf" if value > 0 else "-inf"
        else:
            encoded = repr(value)
        return {"type": "float", "value": encoded}
    return {"type": type(value).__name__, "repr": repr(value)}


def node_record(node: Any) -> dict[str, str]:
    return {"type": type(node).__name__, "repr": repr(node)}


def normalize(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            "kind": "dict",
            "items": [[node_record(k), normalize(v)] for k, v in value.items()],
        }
    if isinstance(value, tuple):
        return {"kind": "tuple", "items": [normalize(v) for v in value]}
    if isinstance(value, list):
        return {"kind": "list", "items": [normalize(v) for v in value]}
    if isinstance(value, (int, float, bool)):
        return number_record(value)
    if value is None:
        return {"kind": "none"}
    return {"kind": "object", "type": type(value).__name__, "repr": repr(value)}


def call_capture(func: Callable[[], Any]) -> dict[str, Any]:
    try:
        return {"ok": True, "value": normalize(func())}
    except Exception as exc:  # noqa: BLE001 - artifact captures public behavior.
        return {
            "ok": False,
            "exception_type": type(exc).__name__,
            "message": str(exc),
        }


def comparable_capture(func: Callable[[], Any]) -> dict[str, Any]:
    captured = call_capture(func)
    return captured


def operation_functions(graph: Any, module: Any, target: int) -> dict[str, Callable[[], Any]]:
    return {
        "dijkstra_path_length": lambda: module.dijkstra_path_length(
            graph, SOURCE, target, weight=WEIGHT
        ),
        "shortest_path_length_weight": lambda: module.shortest_path_length(
            graph, SOURCE, target, weight=WEIGHT
        ),
        "single_source_dijkstra": lambda: module.single_source_dijkstra(
            graph, SOURCE, weight=WEIGHT
        ),
        "dijkstra_predecessor_and_distance": lambda: module.dijkstra_predecessor_and_distance(
            graph, SOURCE, weight=WEIGHT
        ),
    }


def percentile(sorted_values: list[float], pct: float) -> float:
    if not sorted_values:
        return float("nan")
    if len(sorted_values) == 1:
        return sorted_values[0]
    pos = (len(sorted_values) - 1) * pct
    lo = math.floor(pos)
    hi = math.ceil(pos)
    if lo == hi:
        return sorted_values[lo]
    return sorted_values[lo] + (sorted_values[hi] - sorted_values[lo]) * (pos - lo)


def summarize_times(samples_ns: list[int]) -> dict[str, float]:
    values_ms = sorted(ns / 1_000_000.0 for ns in samples_ns)
    return {
        "runs": len(values_ms),
        "min_ms": values_ms[0],
        "p50_ms": statistics.median(values_ms),
        "p95_ms": percentile(values_ms, 0.95),
        "p99_ms": percentile(values_ms, 0.99),
        "max_ms": values_ms[-1],
        "mean_ms": statistics.fmean(values_ms),
    }


def time_callable(func: Callable[[], Any], warmup: int, runs: int) -> tuple[dict[str, float], str]:
    for _ in range(warmup):
        func()
    samples: list[int] = []
    result_digest = ""
    old_gc = gc.isenabled()
    gc.disable()
    try:
        for _ in range(runs):
            start = time.perf_counter_ns()
            result = func()
            end = time.perf_counter_ns()
            samples.append(end - start)
        result_digest = sha256_obj(normalize(result))
    finally:
        if old_gc:
            gc.enable()
    return summarize_times(samples), result_digest


def run_bench(args: argparse.Namespace) -> dict[str, Any]:
    fnx_graph, nx_graph, edges = make_perf_pair(args.nodes, args.extra_edges, SEED)
    target = args.nodes - 1
    fnx_ops = operation_functions(fnx_graph, fnx, target)
    nx_ops = operation_functions(nx_graph, nx, target)
    results: dict[str, Any] = {
        "graph": {
            "kind": "simple_undirected_weighted_graph",
            "nodes": args.nodes,
            "edges": len(edges),
            "seed": SEED,
            "source": SOURCE,
            "target": target,
            "weight": WEIGHT,
        },
        "warmup": args.warmup,
        "runs": args.runs,
        "operations": {},
    }
    for name in fnx_ops:
        fnx_summary, fnx_digest = time_callable(fnx_ops[name], args.warmup, args.runs)
        nx_summary, nx_digest = time_callable(nx_ops[name], args.warmup, args.runs)
        ratio = fnx_summary["p50_ms"] / nx_summary["p50_ms"]
        results["operations"][name] = {
            "fnx": fnx_summary,
            "networkx": nx_summary,
            "fnx_over_networkx_p50": ratio,
            "result_digest_equal": fnx_digest == nx_digest,
            "fnx_result_digest": fnx_digest,
            "networkx_result_digest": nx_digest,
        }
    return results


def profile_callable(
    label: str,
    func: Callable[[], Any],
    repeats: int,
    profile_dir: Path | None,
) -> dict[str, Any]:
    profiler = cProfile.Profile()

    def repeated() -> None:
        for _ in range(repeats):
            func()

    profiler.enable()
    repeated()
    profiler.disable()
    stream = io.StringIO()
    stats = pstats.Stats(profiler, stream=stream).strip_dirs().sort_stats("cumtime")
    stats.print_stats(25)
    text = stream.getvalue()
    if profile_dir is not None:
        profile_dir.mkdir(parents=True, exist_ok=True)
        profiler.dump_stats(str(profile_dir / f"{label}.prof"))
        (profile_dir / f"{label}_top.txt").write_text(text, encoding="utf-8")

    rows = []
    for (filename, line, func_name), stat in stats.stats.items():
        primitive, total_calls, total_time, cumulative, callers = stat
        rows.append(
            {
                "file": filename,
                "line": line,
                "function": func_name,
                "primitive_calls": primitive,
                "total_calls": total_calls,
                "total_time_s": total_time,
                "cumulative_time_s": cumulative,
            }
        )
    rows.sort(key=lambda row: row["cumulative_time_s"], reverse=True)
    return {"label": label, "repeats": repeats, "top_text": text, "top": rows[:25]}


def run_profiles(args: argparse.Namespace, artifact_dir: Path | None) -> dict[str, Any]:
    fnx_graph, nx_graph, edges = make_perf_pair(args.nodes, args.extra_edges, SEED)
    target = args.nodes - 1
    fnx_ops = operation_functions(fnx_graph, fnx, target)
    nx_ops = operation_functions(nx_graph, nx, target)
    for name in fnx_ops:
        fnx_ops[name]()
        nx_ops[name]()
    profile_dir = artifact_dir / "profiles" if artifact_dir is not None else None
    profiles = {
        "graph": {
            "kind": "simple_undirected_weighted_graph",
            "nodes": args.nodes,
            "edges": len(edges),
            "seed": SEED,
        },
        "profile_repeats": args.profile_repeats,
        "profiles": {},
    }
    for name in fnx_ops:
        profiles["profiles"][f"fnx_{name}"] = profile_callable(
            f"fnx_{name}", fnx_ops[name], args.profile_repeats, profile_dir
        )
        profiles["profiles"][f"networkx_{name}"] = profile_callable(
            f"networkx_{name}", nx_ops[name], args.profile_repeats, profile_dir
        )
    return profiles


def golden_cases() -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []

    tie_f = build_from_edges(fnx, make_tie_edges())
    tie_n = build_from_edges(nx, make_tie_edges())
    cases.extend(
        [
            {
                "case": "tie_predecessor_order",
                "operation": "dijkstra_predecessor_and_distance",
                "fnx": comparable_capture(
                    lambda: fnx.dijkstra_predecessor_and_distance(tie_f, "s", weight=WEIGHT)
                ),
                "networkx": comparable_capture(
                    lambda: nx.dijkstra_predecessor_and_distance(tie_n, "s", weight=WEIGHT)
                ),
            },
            {
                "case": "tie_single_source_order",
                "operation": "single_source_dijkstra",
                "fnx": comparable_capture(lambda: fnx.single_source_dijkstra(tie_f, "s", weight=WEIGHT)),
                "networkx": comparable_capture(lambda: nx.single_source_dijkstra(tie_n, "s", weight=WEIGHT)),
            },
            {
                "case": "cutoff_single_source",
                "operation": "single_source_dijkstra_cutoff_2",
                "fnx": comparable_capture(
                    lambda: fnx.single_source_dijkstra(tie_f, "s", cutoff=2, weight=WEIGHT)
                ),
                "networkx": comparable_capture(
                    lambda: nx.single_source_dijkstra(tie_n, "s", cutoff=2, weight=WEIGHT)
                ),
            },
            {
                "case": "cutoff_predecessor",
                "operation": "dijkstra_predecessor_and_distance_cutoff_2",
                "fnx": comparable_capture(
                    lambda: fnx.dijkstra_predecessor_and_distance(
                        tie_f, "s", cutoff=2, weight=WEIGHT
                    )
                ),
                "networkx": comparable_capture(
                    lambda: nx.dijkstra_predecessor_and_distance(
                        tie_n, "s", cutoff=2, weight=WEIGHT
                    )
                ),
            },
        ]
    )

    int_edges = [(0, 1, 2), (1, 2, 3), (0, 2, 9), (2, 3, 4)]
    int_f = build_from_edges(fnx, int_edges)
    int_n = build_from_edges(nx, int_edges)
    cases.extend(
        [
            {
                "case": "int_distance_type_path_length",
                "operation": "dijkstra_path_length",
                "fnx": comparable_capture(lambda: fnx.dijkstra_path_length(int_f, 0, 3, weight=WEIGHT)),
                "networkx": comparable_capture(lambda: nx.dijkstra_path_length(int_n, 0, 3, weight=WEIGHT)),
            },
            {
                "case": "int_distance_type_shortest_path_length",
                "operation": "shortest_path_length_weight",
                "fnx": comparable_capture(lambda: fnx.shortest_path_length(int_f, 0, 3, weight=WEIGHT)),
                "networkx": comparable_capture(lambda: nx.shortest_path_length(int_n, 0, 3, weight=WEIGHT)),
            },
        ]
    )

    mixed_edges = [(0, 1, 2), (1, 2, 1.25), (0, 2, 10), (2, 3, 1)]
    mixed_f = build_from_edges(fnx, mixed_edges)
    mixed_n = build_from_edges(nx, mixed_edges)
    cases.append(
        {
            "case": "mixed_float_distance_type",
            "operation": "single_source_dijkstra",
            "fnx": comparable_capture(lambda: fnx.single_source_dijkstra(mixed_f, 0, weight=WEIGHT)),
            "networkx": comparable_capture(lambda: nx.single_source_dijkstra(mixed_n, 0, weight=WEIGHT)),
        }
    )

    disc_f = build_from_edges(fnx, make_disconnected_edges())
    disc_n = build_from_edges(nx, make_disconnected_edges())
    cases.extend(
        [
            {
                "case": "no_path_error_dijkstra_path_length",
                "operation": "dijkstra_path_length",
                "fnx": comparable_capture(lambda: fnx.dijkstra_path_length(disc_f, "a", "d", weight=WEIGHT)),
                "networkx": comparable_capture(lambda: nx.dijkstra_path_length(disc_n, "a", "d", weight=WEIGHT)),
            },
            {
                "case": "no_path_error_shortest_path_length",
                "operation": "shortest_path_length_weight",
                "fnx": comparable_capture(lambda: fnx.shortest_path_length(disc_f, "a", "d", weight=WEIGHT)),
                "networkx": comparable_capture(lambda: nx.shortest_path_length(disc_n, "a", "d", weight=WEIGHT)),
            },
            {
                "case": "missing_source_single_source",
                "operation": "single_source_dijkstra",
                "fnx": comparable_capture(lambda: fnx.single_source_dijkstra(disc_f, "missing", weight=WEIGHT)),
                "networkx": comparable_capture(lambda: nx.single_source_dijkstra(disc_n, "missing", weight=WEIGHT)),
            },
            {
                "case": "missing_source_predecessor",
                "operation": "dijkstra_predecessor_and_distance",
                "fnx": comparable_capture(
                    lambda: fnx.dijkstra_predecessor_and_distance(disc_f, "missing", weight=WEIGHT)
                ),
                "networkx": comparable_capture(
                    lambda: nx.dijkstra_predecessor_and_distance(disc_n, "missing", weight=WEIGHT)
                ),
            },
        ]
    )

    perf_f, perf_n, edges = make_perf_pair(DEFAULT_NODES, DEFAULT_EXTRA_EDGES, SEED)
    cases.extend(
        [
            {
                "case": "seeded_perf_graph_scalar_path_length",
                "operation": "dijkstra_path_length",
                "graph": {"nodes": DEFAULT_NODES, "edges": len(edges), "seed": SEED},
                "fnx": comparable_capture(
                    lambda: fnx.dijkstra_path_length(perf_f, SOURCE, DEFAULT_NODES - 1, weight=WEIGHT)
                ),
                "networkx": comparable_capture(
                    lambda: nx.dijkstra_path_length(perf_n, SOURCE, DEFAULT_NODES - 1, weight=WEIGHT)
                ),
            },
            {
                "case": "seeded_perf_graph_predecessor_digest",
                "operation": "dijkstra_predecessor_and_distance",
                "graph": {"nodes": DEFAULT_NODES, "edges": len(edges), "seed": SEED},
                "fnx": comparable_capture(
                    lambda: fnx.dijkstra_predecessor_and_distance(perf_f, SOURCE, weight=WEIGHT)
                ),
                "networkx": comparable_capture(
                    lambda: nx.dijkstra_predecessor_and_distance(perf_n, SOURCE, weight=WEIGHT)
                ),
            },
        ]
    )

    for case in cases:
        case["parity_ok"] = case["fnx"] == case["networkx"]
        case["case_digest"] = sha256_obj(case)
    return cases


def run_golden() -> dict[str, Any]:
    cases = golden_cases()
    return {
        "seed": SEED,
        "coverage": [
            "ordering/tie-breaking via dict item order and predecessor list order",
            "int-vs-float distance typing via normalized scalar types",
            "no-path and missing-node exceptions by type and message",
            "cutoff behavior for single_source_dijkstra and predecessor/distance",
            "seeded simple weighted Graph behavior for scalar and predecessor workloads",
            "RNG seed recorded; no randomized algorithm output expected",
        ],
        "cases": cases,
        "all_parity_ok": all(case["parity_ok"] for case in cases),
    }


def env_info() -> dict[str, Any]:
    return {
        "cwd": os.getcwd(),
        "python": sys.version,
        "platform": platform.platform(),
        "git_head": git_output(["git", "rev-parse", "HEAD"]),
        "git_branch": git_output(["git", "rev-parse", "--abbrev-ref", "HEAD"]),
        "git_status_short": git_output(["git", "status", "--short"]),
        "franken_networkx_file": getattr(fnx, "__file__", None),
        "networkx_version": getattr(nx, "__version__", None),
        "networkx_file": getattr(nx, "__file__", None),
    }


def write_json(path: Path, obj: Any) -> None:
    path.write_text(json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["all", "bench", "profile", "golden"], default="all")
    parser.add_argument("--artifact-dir", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--runs", type=int, default=31)
    parser.add_argument("--warmup", type=int, default=5)
    parser.add_argument("--profile-repeats", type=int, default=15)
    parser.add_argument("--nodes", type=int, default=DEFAULT_NODES)
    parser.add_argument("--extra-edges", type=int, default=DEFAULT_EXTRA_EDGES)
    parser.add_argument("--no-write", action="store_true")
    args = parser.parse_args()

    artifact_dir: Path | None = None if args.no_write else args.artifact_dir
    if artifact_dir is not None:
        artifact_dir.mkdir(parents=True, exist_ok=True)

    payload: dict[str, Any] = {"env": env_info()}
    if args.mode in {"all", "golden"}:
        payload["golden"] = run_golden()
    if args.mode in {"all", "bench"}:
        payload["bench"] = run_bench(args)
    if args.mode in {"all", "profile"}:
        payload["profiles"] = run_profiles(args, artifact_dir)

    payload["digest"] = sha256_obj(payload)

    if artifact_dir is not None:
        write_json(artifact_dir / "env.json", payload["env"])
        if "golden" in payload:
            write_json(artifact_dir / "golden_outputs.json", payload["golden"])
            golden_digest = sha256_obj(payload["golden"])
            write_json(
                artifact_dir / "golden_manifest.json",
                {
                    "golden_sha256": golden_digest,
                    "all_parity_ok": payload["golden"]["all_parity_ok"],
                    "coverage": payload["golden"]["coverage"],
                    "case_digests": [
                        {"case": case["case"], "sha256": case["case_digest"]}
                        for case in payload["golden"]["cases"]
                    ],
                },
            )
            golden_file_digest = hashlib.sha256(
                (artifact_dir / "golden_outputs.json").read_bytes()
            ).hexdigest()
            (artifact_dir / "golden.sha256").write_text(
                f"{golden_file_digest}  golden_outputs.json\n", encoding="utf-8"
            )
        if "bench" in payload:
            write_json(artifact_dir / "bench_results.json", payload["bench"])
        if "profiles" in payload:
            profiles_payload = {
                "graph": payload["profiles"]["graph"],
                "profile_repeats": payload["profiles"]["profile_repeats"],
                "profiles": {
                    key: {"label": val["label"], "repeats": val["repeats"], "top": val["top"]}
                    for key, val in payload["profiles"]["profiles"].items()
                },
            }
            write_json(artifact_dir / "profiles_summary.json", profiles_payload)
        write_json(artifact_dir / "pass1_payload_digest.json", {"sha256": payload["digest"]})

    print(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
