#!/usr/bin/env python3
"""Benchmark to_dict_of_dicts residuals for br-r37-c1-p4mqd."""

from __future__ import annotations

import argparse
import cProfile
import hashlib
import io
import json
import pstats
import statistics
import time
from typing import Any

import franken_networkx as fnx
import networkx as nx


def build_graph(module: Any, n: int, p: float) -> Any:
    graph = module.gnp_random_graph(n, p, seed=40017)
    # Keep the target attr-less. The reported p4mqd gap is the empty-edge-attr
    # shallow-copy shape where NetworkX mostly copies neighbor dictionaries.
    return graph


def _py_loop_to_dict_of_dicts(graph: Any) -> dict[Any, dict[Any, Any]]:
    nodelist = list(graph.nodes())
    nodeset = set(nodelist)
    result: dict[Any, dict[Any, Any]] = {}
    is_multigraph = graph.is_multigraph()
    for u in nodelist:
        result[u] = {}
        for v, data in graph[u].items():
            if v in nodeset:
                result[u][v] = data if not is_multigraph else dict(data)
    return result


def _copy_to_dict_of_dicts(graph: Any) -> dict[Any, dict[Any, Any]]:
    return {node: graph[node].copy() for node in graph}


def call_case(module: Any, graph: Any, impl: str) -> Any:
    if impl == "fnx":
        return module.to_dict_of_dicts(graph)
    if impl == "nx":
        return module.to_dict_of_dicts(graph)
    if impl == "py_loop":
        return _py_loop_to_dict_of_dicts(graph)
    if impl == "copy":
        return _copy_to_dict_of_dicts(graph)
    raise ValueError(f"unknown impl: {impl}")


def normalize(result: Any) -> list[tuple[str, list[tuple[str, list[tuple[str, str]]]]]]:
    normalized = []
    for node, neighbors in result.items():
        normalized_neighbors = []
        for neighbor, attrs in neighbors.items():
            normalized_neighbors.append(
                (
                    repr(neighbor),
                    sorted((repr(key), repr(value)) for key, value in dict(attrs).items()),
                )
            )
        normalized.append((repr(node), normalized_neighbors))
    return normalized


def digest(result: Any) -> str:
    payload = json.dumps(normalize(result), separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()


def time_call(func: Any, repeats: int) -> tuple[list[float], Any]:
    samples = []
    last = None
    for _ in range(repeats):
        start = time.perf_counter()
        last = func()
        samples.append(time.perf_counter() - start)
    return samples, last


def bench(args: argparse.Namespace) -> None:
    module = fnx if args.impl != "nx" else nx
    graph = build_graph(module, args.n, args.p)
    samples, result = time_call(lambda: call_case(module, graph, args.impl), args.repeats)
    print(
        json.dumps(
            {
                "impl": args.impl,
                "n": args.n,
                "p": args.p,
                "nodes": graph.number_of_nodes(),
                "edges": graph.number_of_edges(),
                "repeats": args.repeats,
                "mean_sec": statistics.fmean(samples),
                "median_sec": statistics.median(samples),
                "min_sec": min(samples),
                "max_sec": max(samples),
                "samples_sec": samples,
                "digest": digest(result),
            },
            sort_keys=True,
            separators=(",", ":"),
        )
    )


def sweep(args: argparse.Namespace) -> None:
    records = []
    for impl in ("fnx", "nx", "py_loop", "copy"):
        module = fnx if impl != "nx" else nx
        graph = build_graph(module, args.n, args.p)
        samples, result = time_call(lambda: call_case(module, graph, impl), args.repeats)
        records.append(
            {
                "impl": impl,
                "mean_sec": statistics.fmean(samples),
                "median_sec": statistics.median(samples),
                "min_sec": min(samples),
                "max_sec": max(samples),
                "samples_sec": samples,
                "digest": digest(result),
            }
        )
    print(json.dumps({"records": records}, sort_keys=True, separators=(",", ":")))


def golden(args: argparse.Namespace) -> None:
    gx = build_graph(nx, args.n, args.p)
    gf = build_graph(fnx, args.n, args.p)
    nx_result = nx.to_dict_of_dicts(gx)
    fnx_result = fnx.to_dict_of_dicts(gf)
    py_loop_result = _py_loop_to_dict_of_dicts(gf)
    copy_result = _copy_to_dict_of_dicts(gf)
    payload = {
        "nx_digest": digest(nx_result),
        "fnx_digest": digest(fnx_result),
        "py_loop_digest": digest(py_loop_result),
        "copy_digest": digest(copy_result),
        "fnx_matches_nx": normalize(fnx_result) == normalize(nx_result),
        "py_loop_matches_nx": normalize(py_loop_result) == normalize(nx_result),
        "copy_matches_nx": normalize(copy_result) == normalize(nx_result),
        "fnx_identity": next(iter(fnx_result[0].values())) is next(iter(gf[0].values())),
        "py_loop_identity": next(iter(py_loop_result[0].values())) is next(iter(gf[0].values())),
        "copy_identity": next(iter(copy_result[0].values())) is next(iter(gf[0].values())),
    }
    payload["sha256"] = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    print(json.dumps(payload, sort_keys=True, separators=(",", ":")))


def profile(args: argparse.Namespace) -> None:
    module = fnx if args.impl != "nx" else nx
    graph = build_graph(module, args.n, args.p)
    profiler = cProfile.Profile()
    profiler.enable()
    for _ in range(args.repeats):
        call_case(module, graph, args.impl)
    profiler.disable()
    stream = io.StringIO()
    stats = pstats.Stats(profiler, stream=stream).strip_dirs().sort_stats("cumtime")
    stats.print_stats(args.limit)
    print(stream.getvalue(), end="")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=400)
    parser.add_argument("--p", type=float, default=0.02)
    sub = parser.add_subparsers(dest="command", required=True)

    bench_parser = sub.add_parser("bench")
    bench_parser.add_argument("--impl", choices=["fnx", "nx", "py_loop", "copy"], default="fnx")
    bench_parser.add_argument("--repeats", type=int, default=31)
    bench_parser.set_defaults(func=bench)

    sweep_parser = sub.add_parser("sweep")
    sweep_parser.add_argument("--repeats", type=int, default=31)
    sweep_parser.set_defaults(func=sweep)

    golden_parser = sub.add_parser("golden")
    golden_parser.set_defaults(func=golden)

    profile_parser = sub.add_parser("profile")
    profile_parser.add_argument("--impl", choices=["fnx", "nx", "py_loop", "copy"], default="fnx")
    profile_parser.add_argument("--repeats", type=int, default=50)
    profile_parser.add_argument("--limit", type=int, default=40)
    profile_parser.set_defaults(func=profile)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
