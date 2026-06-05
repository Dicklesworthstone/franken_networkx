#!/usr/bin/env python3
"""Benchmark/proof harness for br-r37-c1-tgwv4 weighted all_pairs_dijkstra."""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import time
from collections.abc import Callable
from typing import Any

import franken_networkx as fnx
import networkx as nx
from franken_networkx import _fnx as raw


def _stable(obj: Any) -> Any:
    if isinstance(obj, dict):
        return [[_stable(k), _stable(v)] for k, v in obj.items()]
    if isinstance(obj, (list, tuple)):
        return [_stable(value) for value in obj]
    if isinstance(obj, set):
        return sorted(_stable(value) for value in obj)
    if isinstance(obj, float):
        if obj == float("inf"):
            return "inf"
        if obj == float("-inf"):
            return "-inf"
    return f"{type(obj).__name__}:{obj!r}"


def _digest(value: Any) -> str:
    payload = json.dumps(_stable(value), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def _weighted_path(module: Any, n: int, *, integer: bool = False, directed: bool = False) -> Any:
    graph = module.DiGraph() if directed else module.Graph()
    cast = int if integer else float
    graph.add_weighted_edges_from(
        (i, i + 1, cast((i % 7) + 1)) for i in range(n - 1)
    )
    graph.add_weighted_edges_from(
        (i, i + 2, cast((i % 5) + 3)) for i in range(n - 2)
    )
    return graph


def _mutated_graphs(n: int) -> tuple[Any, Any]:
    fg = _weighted_path(fnx, n, integer=False)
    ng = _weighted_path(nx, n, integer=False)
    dict(fnx.all_pairs_dijkstra(fg, weight="weight"))
    fg[0][2]["weight"] = 1.0
    ng[0][2]["weight"] = 1.0
    return fg, ng


def _coerce_int_distances(value: Any) -> Any:
    out = []
    for source, (dists, paths) in value:
        out.append(
            (
                source,
                (
                    {
                        node: (
                            int(dist)
                            if isinstance(dist, float) and dist.is_integer()
                            else dist
                        )
                        for node, dist in dict(dists).items()
                    },
                    dict(paths),
                ),
            )
        )
    return out


def _run_public(module: Any, graph: Any) -> Any:
    return list(module.all_pairs_dijkstra(graph, weight="weight"))


def _run_raw_native(graph: Any, *, coerce_int: bool = False) -> Any:
    value = list(raw.all_pairs_dijkstra(graph, weight="weight").items())
    if coerce_int:
        return _coerce_int_distances(value)
    return value


def _run_per_source_native(graph: Any) -> Any:
    return [
        (node, fnx.single_source_dijkstra(graph, node, weight="weight"))
        for node in graph.nodes()
    ]


def _sample(label: str, func: Callable[[], Any], repeats: int) -> dict[str, Any]:
    samples: list[float] = []
    digest = ""
    value: Any = None
    for _ in range(repeats):
        started = time.perf_counter()
        value = func()
        samples.append(time.perf_counter() - started)
        digest = _digest(value)
    return {
        "label": label,
        "mean_sec": statistics.fmean(samples),
        "median_sec": statistics.median(samples),
        "min_sec": min(samples),
        "max_sec": max(samples),
        "samples_sec": samples,
        "digest": digest,
        "value": value if repeats == 1 else None,
    }


def bench(args: argparse.Namespace) -> None:
    fg = _weighted_path(fnx, args.size, integer=args.integer, directed=args.directed)
    ng = _weighted_path(nx, args.size, integer=args.integer, directed=args.directed)
    cases = [
        ("fnx_public", lambda: _run_public(fnx, fg)),
        ("networkx", lambda: _run_public(nx, ng)),
        ("raw_native", lambda: _run_raw_native(fg)),
        ("raw_native_coerced", lambda: _run_raw_native(fg, coerce_int=args.integer)),
        ("per_source_native", lambda: _run_per_source_native(fg)),
    ]
    records = [_sample(label, func, args.repeats) for label, func in cases]
    by_label = {record["label"]: record for record in records}
    print(
        json.dumps(
            {
                "size": args.size,
                "integer": args.integer,
                "directed": args.directed,
                "records": [
                    {k: v for k, v in record.items() if k != "value"}
                    for record in records
                ],
                "digests_vs_networkx": {
                    label: record["digest"] == by_label["networkx"]["digest"]
                    for label, record in by_label.items()
                },
                "mean_over_networkx": {
                    label: record["mean_sec"] / by_label["networkx"]["mean_sec"]
                    for label, record in by_label.items()
                },
            },
            sort_keys=True,
            separators=(",", ":"),
        ),
        flush=True,
    )


def golden(args: argparse.Namespace) -> None:
    outputs: dict[str, Any] = {}
    for name, integer, directed in (
        ("float_graph", False, False),
        ("int_graph", True, False),
        ("float_digraph", False, True),
    ):
        fg = _weighted_path(fnx, args.size, integer=integer, directed=directed)
        ng = _weighted_path(nx, args.size, integer=integer, directed=directed)
        outputs[name] = {
            "fnx_public": _run_public(fnx, fg),
            "networkx": _run_public(nx, ng),
            "raw_native": _run_raw_native(fg),
            "raw_native_coerced": _run_raw_native(fg, coerce_int=integer),
        }
    fg_mut, ng_mut = _mutated_graphs(args.size)
    outputs["mutated_float_graph"] = {
        "fnx_public": _run_public(fnx, fg_mut),
        "networkx": _run_public(nx, ng_mut),
        "raw_native": _run_raw_native(fg_mut),
    }
    digests = {
        case: {label: _digest(value) for label, value in values.items()}
        for case, values in outputs.items()
    }
    print(
        json.dumps(
            {
                "size": args.size,
                "digests": digests,
                "equals_networkx": {
                    case: {
                        label: value == values["networkx"]
                        for label, value in values.items()
                    }
                    for case, values in outputs.items()
                },
                "sha256": _digest(outputs),
            },
            sort_keys=True,
            separators=(",", ":"),
        ),
        flush=True,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    bench_parser = sub.add_parser("bench")
    bench_parser.add_argument("--size", type=int, default=80)
    bench_parser.add_argument("--repeats", type=int, default=7)
    bench_parser.add_argument("--integer", action="store_true")
    bench_parser.add_argument("--directed", action="store_true")
    golden_parser = sub.add_parser("golden")
    golden_parser.add_argument("--size", type=int, default=24)
    args = parser.parse_args()
    if args.cmd == "bench":
        bench(args)
    else:
        golden(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
