#!/usr/bin/env python3
"""Benchmark and golden check for distance-measures kernels."""

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


def distance_payload(module: Any, graph: Any) -> dict[str, Any]:
    ecc = module.eccentricity(graph)
    return {
        "diameter": module.diameter(graph),
        "radius": module.radius(graph),
        "center": [repr(node) for node in module.center(graph)],
        "periphery": [repr(node) for node in module.periphery(graph)],
        "eccentricity": sorted((repr(node), value) for node, value in ecc.items()),
    }


def digest_payload(payload: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def sample(module: Any, graph: Any, op: str, repeats: int) -> tuple[list[float], Any]:
    samples = []
    result = None
    func = getattr(module, op)
    for _ in range(repeats):
        start = time.perf_counter()
        result = func(graph)
        samples.append(time.perf_counter() - start)
    return samples, result


def emit_record(
    impl: str,
    op: str,
    n: int,
    m: int,
    seed: int,
    repeats: int,
    samples: list[float],
    result: Any,
    graph: Any,
    module: Any,
) -> None:
    payload = distance_payload(module, graph)
    print(
        json.dumps(
            {
                "case": "distance_measures_ba",
                "impl": impl,
                "op": op,
                "n": n,
                "m": m,
                "seed": seed,
                "repeats": repeats,
                "mean_sec": statistics.fmean(samples),
                "median_sec": statistics.median(samples),
                "min_sec": min(samples),
                "max_sec": max(samples),
                "samples_sec": samples,
                "result": result,
                "digest": digest_payload(payload),
            },
            sort_keys=True,
            separators=(",", ":"),
        ),
        flush=True,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("sample", "profile", "golden"))
    parser.add_argument("--impl", choices=("fnx", "nx"), default="fnx")
    parser.add_argument("--op", choices=("diameter", "eccentricity"), default="diameter")
    parser.add_argument("--n", type=int, default=1200)
    parser.add_argument("--m", type=int, default=5)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--profile-output", default="")
    parser.add_argument("--profile-limit", type=int, default=80)
    args = parser.parse_args()

    fnx_graph, nx_graph = build_pair(args.n, args.m, args.seed)
    module = fnx if args.impl == "fnx" else nx
    graph = fnx_graph if args.impl == "fnx" else nx_graph

    if args.mode == "golden":
        fnx_payload = distance_payload(fnx, fnx_graph)
        nx_payload = distance_payload(nx, nx_graph)
        print(
            json.dumps(
                {
                    "fnx_digest": digest_payload(fnx_payload),
                    "nx_digest": digest_payload(nx_payload),
                    "equal": fnx_payload == nx_payload,
                    "payload": fnx_payload,
                },
                sort_keys=True,
                separators=(",", ":"),
            )
        )
        return 0

    # Warm imports and dispatch outside the timed region.
    getattr(module, args.op)(graph)

    if args.mode == "profile":
        profiler = cProfile.Profile()
        profiler.enable()
        samples, result = sample(module, graph, args.op, args.repeats)
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
        samples, result = sample(module, graph, args.op, args.repeats)

    emit_record(
        args.impl,
        args.op,
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
