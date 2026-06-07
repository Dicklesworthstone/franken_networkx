#!/usr/bin/env python3
"""Proof and benchmark for br-r37-c1-d58s8 DiGraph generator ctor ingest."""

from __future__ import annotations

import argparse
import cProfile
import hashlib
import io
import json
import pstats
import random
import statistics
import time
from collections.abc import Callable, Iterable, Iterator
from typing import Any

import franken_networkx as fnx
import networkx as nx


def plain_edges(n: int = 1500, m: int = 6000, seed: int = 41) -> list[tuple[int, int]]:
    rng = random.Random(seed)
    edges = [(i, (i * 17 + 1) % n) for i in range(n)]
    while len(edges) < m:
        u = rng.randrange(n)
        v = rng.randrange(n)
        if u != v:
            edges.append((u, v))
    return edges


def attr_edges(
    n: int = 1500, m: int = 6000, seed: int = 43
) -> list[tuple[int, int, dict[str, Any]]]:
    return [
        (
            u,
            v,
            {
                "w": (u * 131 + v) % 997,
                "label": f"{u}->{v}",
                "flag": (u + v) % 2 == 0,
            },
        )
        for u, v in plain_edges(n, m, seed)
    ]


def generator_from(edges: Iterable[Any]) -> Iterator[Any]:
    for edge in edges:
        yield edge


def canonical(graph: Any) -> dict[str, Any]:
    return {
        "nodes": [
            [repr(node), sorted(dict(attrs).items(), key=lambda item: repr(item[0]))]
            for node, attrs in graph.nodes(data=True)
        ],
        "edges": [
            [repr(u), repr(v), sorted(dict(attrs).items(), key=lambda item: repr(item[0]))]
            for u, v, attrs in graph.edges(data=True)
        ],
        "succ": {
            repr(node): [repr(neighbor) for neighbor in graph.succ[node]]
            for node in graph.nodes()
        },
        "pred": {
            repr(node): [repr(neighbor) for neighbor in graph.pred[node]]
            for node in graph.nodes()
        },
        "graph": sorted(graph.graph.items(), key=lambda item: repr(item[0])),
    }


def build_ctor(lib: Any, edges: list[Any], graph_attr: dict[str, Any] | None = None) -> Any:
    if graph_attr is None:
        return lib.DiGraph(generator_from(edges))
    return lib.DiGraph(generator_from(edges), **graph_attr)


def apply_case(lib: Any, case: dict[str, Any]) -> dict[str, Any]:
    try:
        graph = build_ctor(lib, case["edges"], case.get("graph_attr"))
    except Exception as exc:  # noqa: BLE001 - exception shape is part of parity.
        return {"error_type": type(exc).__name__, "error": str(exc)}

    result = {"graph": canonical(graph)}
    if case.get("mutate_empty_edge_dict"):
        # NetworkX returns live empty dicts for edges(data=True). This catches
        # accidental lazy-mirror behavior that hands back detached empty dicts.
        u, v, attrs = next(iter(graph.edges(data=True)))
        attrs["touched"] = True
        result["post_edge_data_mutation"] = list(graph.edges(data=True))[0][2]
        result["post_lookup"] = dict(graph[u][v])
    return result


def proof_cases() -> list[dict[str, Any]]:
    return [
        {
            "name": "plain_generator",
            "edges": [(0, 1), (1, 2), (2, 0), (2, 0), (3, 3)],
            "mutate_empty_edge_dict": True,
        },
        {
            "name": "attr_generator",
            "edges": [
                (0, 1, {"w": 1, "label": "a"}),
                (1, 2, {"w": 2}),
                (0, 1, {"extra": True}),
                (3, 3, {"self": "loop"}),
            ],
        },
        {
            "name": "interleaved_slow_node",
            "edges": [(0, 1), "sentinel", (2, 3, {"w": 3}), (3, 4)],
        },
        {
            "name": "bad_third_hashable",
            "edges": [(0, 1), (9, 9, 9), (1, 2)],
        },
        {
            "name": "bad_third_unhashable",
            "edges": [(0, 1), (9, 9, {"x": []}), (1, 2)],
        },
        {
            "name": "graph_attr",
            "edges": [(0, 1), (1, 2)],
            "graph_attr": {"name": "ctor-gen", "payload": [1, 2]},
        },
    ]


def run_proof() -> None:
    results = []
    for case in proof_cases():
        fnx_result = apply_case(fnx, case)
        nx_result = apply_case(nx, case)
        results.append(
            {
                "case": case["name"],
                "fnx": fnx_result,
                "matches_nx": fnx_result == nx_result,
                "nx": nx_result,
            }
        )
    blob = json.dumps(results, sort_keys=True, separators=(",", ":"), default=repr).encode()
    print(
        json.dumps(
            {
                "cases": len(results),
                "golden_sha256": hashlib.sha256(blob).hexdigest(),
                "results": results,
            },
            sort_keys=True,
        )
    )


def best_time(func: Callable[[], Any], loops: int, samples: int) -> dict[str, float]:
    times = []
    for _ in range(samples):
        start = time.perf_counter()
        for _ in range(loops):
            result = func()
            if result.number_of_edges() <= 0:
                raise AssertionError("unexpected empty graph")
        times.append((time.perf_counter() - start) / loops)
    return {
        "best_s": min(times),
        "mean_s": statistics.mean(times),
        "median_s": statistics.median(times),
    }


def run_bench() -> None:
    scenarios = [
        ("generator_plain", plain_edges(), 12),
        ("generator_attr", attr_edges(), 8),
    ]
    rows = []
    for name, edges, loops in scenarios:
        fnx_stats = best_time(lambda edges=edges: build_ctor(fnx, edges), loops, 7)
        nx_stats = best_time(lambda edges=edges: build_ctor(nx, edges), loops, 7)
        rows.append(
            {
                "edges": len(edges),
                "fnx": fnx_stats,
                "fnx_vs_nx_best_ratio": fnx_stats["best_s"] / nx_stats["best_s"],
                "name": name,
                "nx": nx_stats,
            }
        )
    print(json.dumps({"scenarios": rows}, indent=2, sort_keys=True))


def profile_body() -> None:
    plain = plain_edges()
    attributed = attr_edges()
    for _ in range(80):
        build_ctor(fnx, plain)
        build_ctor(fnx, attributed)


def run_profile() -> None:
    profiler = cProfile.Profile()
    profiler.enable()
    profile_body()
    profiler.disable()
    stream = io.StringIO()
    pstats.Stats(profiler, stream=stream).sort_stats("cumtime").print_stats(40)
    print(stream.getvalue())


def run_fnx_loop(kind: str, loops: int) -> None:
    edges = plain_edges() if kind == "plain" else attr_edges()
    total = 0
    for _ in range(loops):
        total += build_ctor(fnx, edges).number_of_edges()
    print(json.dumps({"kind": kind, "loops": loops, "total_edges": total}, sort_keys=True))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "mode",
        choices=["proof", "bench", "profile", "fnx-loop-plain", "fnx-loop-attr"],
    )
    parser.add_argument("--loops", type=int, default=30)
    args = parser.parse_args()
    if args.mode == "proof":
        run_proof()
    elif args.mode == "bench":
        run_bench()
    elif args.mode == "profile":
        run_profile()
    elif args.mode == "fnx-loop-plain":
        run_fnx_loop("plain", args.loops)
    else:
        run_fnx_loop("attr", args.loops)


if __name__ == "__main__":
    main()
