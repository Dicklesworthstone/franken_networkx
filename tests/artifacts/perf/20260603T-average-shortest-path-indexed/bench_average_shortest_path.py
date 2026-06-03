#!/usr/bin/env python3
"""Benchmark and golden check for average_shortest_path_length."""

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

import franken_networkx as fnx
import networkx as nx


def build_pair(kind: str, n: int, m: int, seed: int) -> tuple[Any, Any]:
    if kind == "ba":
        base = nx.barabasi_albert_graph(n, m, seed=seed)
    elif kind == "path":
        base = nx.path_graph(n)
    elif kind == "cycle":
        base = nx.cycle_graph(n)
    elif kind == "complete":
        base = nx.complete_graph(n)
    elif kind == "disconnected":
        base = nx.Graph()
        base.add_nodes_from(range(n))
        split = max(1, n // 2)
        base.add_edges_from((i, i + 1) for i in range(split - 1))
        base.add_edges_from((i, i + 1) for i in range(split, n - 1))
    else:
        raise ValueError(f"unknown graph kind: {kind}")

    graph = fnx.Graph()
    graph.add_nodes_from(base.nodes())
    graph.add_edges_from(base.edges())
    return graph, base


def result_payload(module: Any, graph: Any) -> dict[str, Any]:
    try:
        value = module.average_shortest_path_length(graph)
    except Exception as exc:  # noqa: BLE001 - golden captures public exception class/text.
        return {
            "ok": False,
            "error_type": type(exc).__name__,
            "error_text": str(exc),
        }
    if isinstance(value, float) and not math.isfinite(value):
        value_repr = "inf" if value > 0 else "-inf"
    else:
        value_repr = repr(value)
    return {"ok": True, "value": value_repr}


def digest_payload(payload: Any) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def sample(module: Any, graph: Any, repeats: int) -> tuple[list[float], Any]:
    samples = []
    result = None
    for _ in range(repeats):
        start = time.perf_counter()
        result = module.average_shortest_path_length(graph)
        samples.append(time.perf_counter() - start)
    return samples, result


def emit_record(
    impl: str,
    kind: str,
    n: int,
    m: int,
    seed: int,
    repeats: int,
    samples: list[float],
    result: Any,
    graph: Any,
    module: Any,
) -> None:
    payload = result_payload(module, graph)
    print(
        json.dumps(
            {
                "case": "average_shortest_path_length",
                "impl": impl,
                "kind": kind,
                "n": n,
                "m": m,
                "seed": seed,
                "repeats": repeats,
                "mean_sec": statistics.fmean(samples),
                "median_sec": statistics.median(samples),
                "min_sec": min(samples),
                "max_sec": max(samples),
                "samples_sec": samples,
                "result": repr(result),
                "digest": digest_payload(payload),
            },
            sort_keys=True,
            separators=(",", ":"),
        ),
        flush=True,
    )


def golden_cases() -> list[tuple[str, int, int, int]]:
    return [
        ("path", 8, 1, 0),
        ("cycle", 9, 1, 0),
        ("complete", 7, 1, 0),
        ("ba", 80, 3, 42),
        ("ba", 120, 5, 17),
        ("disconnected", 10, 1, 0),
    ]


def emit_golden() -> int:
    cases = []
    for kind, n, m, seed in golden_cases():
        fnx_graph, nx_graph = build_pair(kind, n, m, seed)
        fnx_payload = result_payload(fnx, fnx_graph)
        nx_payload = result_payload(nx, nx_graph)
        cases.append(
            {
                "kind": kind,
                "n": n,
                "m": m,
                "seed": seed,
                "fnx": fnx_payload,
                "nx": nx_payload,
                "equal": fnx_payload == nx_payload,
            }
        )
    payload = {"cases": cases}
    print(
        json.dumps(
            {
                "digest": digest_payload(payload),
                "all_equal": all(case["equal"] for case in cases),
                "payload": payload,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
    )
    return 0 if all(case["equal"] for case in cases) else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("sample", "profile", "golden"))
    parser.add_argument("--impl", choices=("fnx", "nx"), default="fnx")
    parser.add_argument("--kind", choices=("ba", "path", "cycle", "complete"), default="ba")
    parser.add_argument("--n", type=int, default=1200)
    parser.add_argument("--m", type=int, default=5)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--profile-output", default="")
    parser.add_argument("--profile-limit", type=int, default=80)
    args = parser.parse_args()

    if args.mode == "golden":
        return emit_golden()

    fnx_graph, nx_graph = build_pair(args.kind, args.n, args.m, args.seed)
    module = fnx if args.impl == "fnx" else nx
    graph = fnx_graph if args.impl == "fnx" else nx_graph

    # Warm imports and dispatch outside the timed region.
    module.average_shortest_path_length(graph)

    if args.mode == "profile":
        profiler = cProfile.Profile()
        profiler.enable()
        samples, result = sample(module, graph, args.repeats)
        profiler.disable()
        stream = io.StringIO()
        pstats.Stats(profiler, stream=stream).strip_dirs().sort_stats(
            "cumtime"
        ).print_stats(args.profile_limit)
        if args.profile_output:
            Path(args.profile_output).write_text(stream.getvalue(), encoding="utf-8")
        else:
            print(stream.getvalue())
    else:
        samples, result = sample(module, graph, args.repeats)

    emit_record(
        args.impl,
        args.kind,
        args.n,
        args.m,
        args.seed,
        args.repeats,
        samples,
        result,
        graph,
        module,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
