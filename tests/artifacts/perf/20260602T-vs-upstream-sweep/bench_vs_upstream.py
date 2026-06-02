#!/usr/bin/env python3
"""Profile residual fnx-vs-networkx sparse matrix gaps.

This is a measurement artifact for the no-gaps performance campaign, not a
library module. It deliberately keeps graph construction deterministic and
prints compact JSON records so hyperfine/cProfile output can be archived.
"""

from __future__ import annotations

import argparse
import cProfile
import hashlib
import io
import json
import pstats
import statistics
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import networkx as nx

import franken_networkx as fnx


def _edge_weight(u: int, v: int) -> float:
    return float(((u * 1315423911 + v * 2654435761) & 15) + 1)


def _build_graphs(n: int, m: int, *, weighted: bool) -> tuple[Any, Any]:
    nx_graph = nx.barabasi_albert_graph(n, m, seed=12345)
    fnx_graph = fnx.Graph()
    fnx_graph.add_nodes_from(nx_graph.nodes())
    for u, v in nx_graph.edges():
        if weighted:
            weight = _edge_weight(int(u), int(v))
            nx_graph.edges[u, v]["weight"] = weight
            fnx_graph.add_edge(u, v, weight=weight)
        else:
            fnx_graph.add_edge(u, v)
    return fnx_graph, nx_graph


def _matrix_digest(matrix: Any) -> str:
    coo = matrix.tocoo()
    payload = b"|".join(
        [
            str(matrix.shape).encode(),
            str(matrix.dtype).encode(),
            coo.row.astype("<i8", copy=False).tobytes(),
            coo.col.astype("<i8", copy=False).tobytes(),
            coo.data.tobytes(),
        ]
    )
    return hashlib.sha256(payload).hexdigest()


def _hits_digest(result: Any) -> str:
    hubs, authorities = result
    payload = json.dumps(
        {
            "hubs": [(node, float(hubs[node])) for node in hubs],
            "authorities": [(node, float(authorities[node])) for node in authorities],
        },
        separators=(",", ":"),
    ).encode()
    return hashlib.sha256(payload).hexdigest()


def _call_case(module: Any, graph: Any, case: str) -> Any:
    if case == "adjacency_default":
        return module.adjacency_matrix(graph)
    if case == "adjacency_weighted_float":
        return module.adjacency_matrix(graph, dtype=float, weight="weight")
    if case == "to_scipy_default":
        return module.to_scipy_sparse_array(graph)
    if case == "to_scipy_weighted_float":
        return module.to_scipy_sparse_array(graph, dtype=float, weight="weight")
    if case == "laplacian_default":
        return module.laplacian_matrix(graph)
    if case == "normalized_laplacian_default":
        return module.normalized_laplacian_matrix(graph)
    if case == "hits":
        nstart = {node: 1.0 for node in graph}
        return module.hits(graph, nstart=nstart, max_iter=300, tol=1.0e-8)
    raise ValueError(f"unknown case: {case}")


def _digest(case: str, result: Any) -> str:
    if case == "hits":
        return _hits_digest(result)
    return _matrix_digest(result)


def _time_call(func: Callable[[], Any], repeats: int) -> tuple[list[float], Any]:
    samples: list[float] = []
    last: Any = None
    for _ in range(repeats):
        start = time.perf_counter()
        last = func()
        samples.append(time.perf_counter() - start)
    return samples, last


def _emit(record: dict[str, Any]) -> None:
    print(json.dumps(record, sort_keys=True, separators=(",", ":")), flush=True)


def run_once(args: argparse.Namespace) -> int:
    weighted = args.case.endswith("_weighted_float")
    fnx_graph, nx_graph = _build_graphs(args.n, args.m, weighted=weighted)
    module = fnx if args.impl == "fnx" else nx
    graph = fnx_graph if args.impl == "fnx" else nx_graph
    result = _call_case(module, graph, args.case)
    _emit(
        {
            "case": args.case,
            "impl": args.impl,
            "n": args.n,
            "m": args.m,
            "nodes": len(graph),
            "edges": graph.number_of_edges(),
            "digest": _digest(args.case, result),
        }
    )
    return 0


def run_sweep(args: argparse.Namespace) -> int:
    cases = [
        "adjacency_default",
        "adjacency_weighted_float",
        "to_scipy_default",
        "to_scipy_weighted_float",
        "laplacian_default",
        "normalized_laplacian_default",
    ]
    for case in cases:
        weighted = case.endswith("_weighted_float")
        fnx_graph, nx_graph = _build_graphs(args.n, args.m, weighted=weighted)
        records = []
        for impl, module, graph in (
            ("fnx", fnx, fnx_graph),
            ("nx", nx, nx_graph),
        ):
            samples, result = _time_call(
                lambda module=module, graph=graph, case=case: _call_case(
                    module, graph, case
                ),
                args.repeats,
            )
            records.append(
                {
                    "impl": impl,
                    "mean_sec": statistics.fmean(samples),
                    "median_sec": statistics.median(samples),
                    "min_sec": min(samples),
                    "max_sec": max(samples),
                    "samples_sec": samples,
                    "digest": _digest(case, result),
                }
            )
        fnx_rec, nx_rec = records
        _emit(
            {
                "case": case,
                "n": args.n,
                "m": args.m,
                "edges": fnx_graph.number_of_edges(),
                "fnx": fnx_rec,
                "nx": nx_rec,
                "fnx_over_nx": fnx_rec["mean_sec"] / nx_rec["mean_sec"],
                "digests_match": fnx_rec["digest"] == nx_rec["digest"],
            }
        )
    return 0


def run_bench(args: argparse.Namespace) -> int:
    weighted = args.case.endswith("_weighted_float")
    fnx_graph, nx_graph = _build_graphs(args.n, args.m, weighted=weighted)
    module = fnx if args.impl == "fnx" else nx
    graph = fnx_graph if args.impl == "fnx" else nx_graph
    samples, result = _time_call(
        lambda: _call_case(module, graph, args.case),
        args.repeats,
    )
    _emit(
        {
            "case": args.case,
            "impl": args.impl,
            "n": args.n,
            "m": args.m,
            "edges": graph.number_of_edges(),
            "repeats": args.repeats,
            "mean_sec": statistics.fmean(samples),
            "median_sec": statistics.median(samples),
            "min_sec": min(samples),
            "max_sec": max(samples),
            "samples_sec": samples,
            "digest": _digest(args.case, result),
        }
    )
    return 0


def run_profile(args: argparse.Namespace) -> int:
    weighted = args.case.endswith("_weighted_float")
    fnx_graph, nx_graph = _build_graphs(args.n, args.m, weighted=weighted)
    module = fnx if args.impl == "fnx" else nx
    graph = fnx_graph if args.impl == "fnx" else nx_graph
    profiler = cProfile.Profile()
    profiler.enable()
    result = None
    for _ in range(args.repeats):
        result = _call_case(module, graph, args.case)
    profiler.disable()
    stream = io.StringIO()
    pstats.Stats(profiler, stream=stream).strip_dirs().sort_stats("cumtime").print_stats(
        args.limit
    )
    output_path = Path(args.output)
    output_path.write_text(stream.getvalue(), encoding="utf-8")
    _emit(
        {
            "case": args.case,
            "impl": args.impl,
            "n": args.n,
            "m": args.m,
            "repeats": args.repeats,
            "digest": _digest(args.case, result),
            "profile": str(output_path),
        }
    )
    return 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="cmd", required=True)

    once = subparsers.add_parser("once")
    once.add_argument("--case", required=True)
    once.add_argument("--impl", choices=("fnx", "nx"), required=True)
    once.add_argument("--n", type=int, default=8000)
    once.add_argument("--m", type=int, default=4)
    once.set_defaults(func=run_once)

    sweep = subparsers.add_parser("sweep")
    sweep.add_argument("--n", type=int, default=8000)
    sweep.add_argument("--m", type=int, default=4)
    sweep.add_argument("--repeats", type=int, default=5)
    sweep.set_defaults(func=run_sweep)

    bench = subparsers.add_parser("bench")
    bench.add_argument("--case", required=True)
    bench.add_argument("--impl", choices=("fnx", "nx"), required=True)
    bench.add_argument("--n", type=int, default=8000)
    bench.add_argument("--m", type=int, default=4)
    bench.add_argument("--repeats", type=int, default=8)
    bench.set_defaults(func=run_bench)

    profile = subparsers.add_parser("profile")
    profile.add_argument("--case", required=True)
    profile.add_argument("--impl", choices=("fnx", "nx"), required=True)
    profile.add_argument("--n", type=int, default=8000)
    profile.add_argument("--m", type=int, default=4)
    profile.add_argument("--repeats", type=int, default=5)
    profile.add_argument("--limit", type=int, default=35)
    profile.add_argument("--output", required=True)
    profile.set_defaults(func=run_profile)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
