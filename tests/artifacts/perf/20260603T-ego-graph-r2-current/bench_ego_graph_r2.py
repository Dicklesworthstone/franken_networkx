#!/usr/bin/env python3
"""Focused ego_graph(radius=2) benchmark for the no-gaps perf campaign."""

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

import franken_networkx as fnx
import networkx as nx


def build_pair(n: int, m: int, seed: int) -> tuple[Any, Any]:
    base = nx.barabasi_albert_graph(n, m, seed=seed)
    graph = fnx.Graph()
    graph.add_nodes_from(base.nodes())
    graph.add_edges_from(base.edges())
    return graph, base


def normalize_graph(graph: Any) -> dict[str, list[Any]]:
    return {
        "nodes": sorted(repr(node) for node in graph.nodes()),
        "edges": sorted((repr(u), repr(v)) for u, v in graph.edges()),
    }


def digest_graph(graph: Any) -> str:
    payload = json.dumps(
        normalize_graph(graph), sort_keys=True, separators=(",", ":")
    ).encode()
    return hashlib.sha256(payload).hexdigest()


def sample(module: Any, graph: Any, repeats: int) -> tuple[list[float], Any]:
    samples = []
    result = None
    for _ in range(repeats):
        start = time.perf_counter()
        result = module.ego_graph(graph, 0, radius=2)
        samples.append(time.perf_counter() - start)
    return samples, result


def emit_record(impl: str, n: int, m: int, seed: int, repeats: int, samples, result) -> None:
    print(
        json.dumps(
            {
                "case": "ego_graph_r2",
                "impl": impl,
                "n": n,
                "m": m,
                "seed": seed,
                "repeats": repeats,
                "mean_sec": statistics.fmean(samples),
                "median_sec": statistics.median(samples),
                "min_sec": min(samples),
                "max_sec": max(samples),
                "samples_sec": samples,
                "digest": digest_graph(result),
            },
            sort_keys=True,
            separators=(",", ":"),
        ),
        flush=True,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("sample", "profile"))
    parser.add_argument("--impl", choices=("fnx", "nx"), default="fnx")
    parser.add_argument("--n", type=int, default=3000)
    parser.add_argument("--m", type=int, default=4)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--repeats", type=int, default=7)
    parser.add_argument("--profile-output", default="")
    parser.add_argument("--profile-limit", type=int, default=80)
    args = parser.parse_args()

    fnx_graph, nx_graph = build_pair(args.n, args.m, args.seed)
    module = fnx if args.impl == "fnx" else nx
    graph = fnx_graph if args.impl == "fnx" else nx_graph

    # Warm the dispatch/import path so profile samples focus on ego_graph.
    module.ego_graph(graph, 0, radius=2)

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

    emit_record(args.impl, args.n, args.m, args.seed, args.repeats, samples, result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
