#!/usr/bin/env python3
"""Proof/profile harness for br-r37-c1-04z53.9108."""

from __future__ import annotations

import argparse
import cProfile
import hashlib
import json
import pstats
import statistics
import time
from pathlib import Path
from typing import Any, Callable

import networkx as nx

import franken_networkx as fnx


def _nx_simrank() -> Callable[..., Any]:
    return getattr(nx.simrank_similarity, "orig_func", nx.simrank_similarity)


def _to_fnx(graph: Any) -> Any:
    if graph.is_directed():
        out = fnx.DiGraph()
    else:
        out = fnx.Graph()
    out.add_nodes_from(graph.nodes(data=True))
    out.add_edges_from(graph.edges(data=True))
    return out


def _corpus() -> list[tuple[str, Any, Any, Any, Any]]:
    cases: list[tuple[str, Any, Any, Any, Any]] = []
    base = nx.connected_watts_strogatz_graph(220, 8, 0.3, seed=7)
    cases.append(("ws220_pair", base, 0, 10, "pair"))
    cases.append(("ws220_source", base, 0, None, "source"))
    path = nx.path_graph(32)
    cases.append(("path32_pair", path, 2, 25, "pair"))
    directed = nx.gn_graph(48, seed=3)
    cases.append(("gn48_pair", directed, 0, 20, "pair"))
    return [(name, graph, _to_fnx(graph), source, target) for name, graph, source, target, _kind in cases]


def _stable_payload(value: Any) -> Any:
    if isinstance(value, float):
        return repr(value)
    if isinstance(value, dict):
        return [
            (repr(key), _stable_payload(inner))
            for key, inner in value.items()
        ]
    return repr(value)


def _digest(value: Any) -> str:
    payload = json.dumps(_stable_payload(value), separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _run(kind: str, graph: Any, fnx_graph: Any, source: Any, target: Any) -> Any:
    if kind == "fnx":
        return fnx.simrank_similarity(fnx_graph, source=source, target=target)
    if kind == "nx":
        return _nx_simrank()(graph, source=source, target=target)
    raise ValueError(kind)


def proof() -> dict[str, Any]:
    rows = []
    for name, graph, fnx_graph, source, target in _corpus():
        actual = _run("fnx", graph, fnx_graph, source, target)
        expected = _run("nx", graph, fnx_graph, source, target)
        rows.append(
            {
                "name": name,
                "source": repr(source),
                "target": repr(target),
                "fnx_sha256": _digest(actual),
                "nx_sha256": _digest(expected),
                "match": actual == expected,
            }
        )
    bundle = hashlib.sha256(
        json.dumps(rows, separators=(",", ":"), sort_keys=True).encode("utf-8")
    ).hexdigest()
    return {
        "bundle_sha256": bundle,
        "rows": rows,
        "all_match": all(row["match"] for row in rows),
    }


def bench(kind: str, repeats: int) -> dict[str, Any]:
    graph = nx.connected_watts_strogatz_graph(220, 8, 0.3, seed=7)
    fnx_graph = _to_fnx(graph)
    timings = []
    result = None
    for _ in range(1):
        result = _run(kind, graph, fnx_graph, 0, 10)
    for _ in range(repeats):
        start = time.perf_counter()
        result = _run(kind, graph, fnx_graph, 0, 10)
        timings.append(time.perf_counter() - start)
    return {
        "kind": kind,
        "repeats": repeats,
        "median_s": statistics.median(timings),
        "mean_s": statistics.fmean(timings),
        "min_s": min(timings),
        "max_s": max(timings),
        "result_repr": repr(result),
        "result_sha256": _digest(result),
    }


def profile(kind: str, repeats: int, output: Path) -> dict[str, Any]:
    graph = nx.connected_watts_strogatz_graph(220, 8, 0.3, seed=7)
    fnx_graph = _to_fnx(graph)

    def run() -> None:
        for _ in range(repeats):
            _run(kind, graph, fnx_graph, 0, 10)

    profiler = cProfile.Profile()
    profiler.runcall(run)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as handle:
        pstats.Stats(profiler, stream=handle).strip_dirs().sort_stats("cumtime").print_stats(60)
    return {"kind": kind, "profile": str(output), "repeats": repeats}


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("proof")
    bench_parser = sub.add_parser("bench")
    bench_parser.add_argument("--kind", choices=["fnx", "nx"], required=True)
    bench_parser.add_argument("--repeats", type=int, default=3)
    profile_parser = sub.add_parser("profile")
    profile_parser.add_argument("--kind", choices=["fnx", "nx"], required=True)
    profile_parser.add_argument("--repeats", type=int, default=1)
    profile_parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    if args.cmd == "proof":
        result = proof()
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if result["all_match"] else 1
    if args.cmd == "bench":
        print(json.dumps(bench(args.kind, args.repeats), indent=2, sort_keys=True))
        return 0
    if args.cmd == "profile":
        print(json.dumps(profile(args.kind, args.repeats, args.output), indent=2, sort_keys=True))
        return 0
    raise AssertionError(args.cmd)


if __name__ == "__main__":
    raise SystemExit(main())
