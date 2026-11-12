#!/usr/bin/env python3
"""Proof and benchmark for Graph constructor PyList extraction."""

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


def plain_edges(n: int = 3000, m: int = 12000, seed: int = 71) -> list[tuple[int, int]]:
    rng = random.Random(seed)
    edges = [(i, (i * 17 + 5) % n) for i in range(n)]
    while len(edges) < m:
        u = rng.randrange(n)
        v = rng.randrange(n)
        if u != v:
            edges.append((u, v))
    return edges


def attr_edges(
    n: int = 2600, m: int = 9000, seed: int = 73
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
        "adj": {
            repr(node): [
                [repr(neighbor), sorted(dict(attrs).items(), key=lambda item: repr(item[0]))]
                for neighbor, attrs in graph.adj[node].items()
            ]
            for node in graph.nodes()
        },
        "graph": sorted(graph.graph.items(), key=lambda item: repr(item[0])),
    }


def input_for_kind(kind: str, edges: list[Any]) -> Any:
    if kind == "list":
        return list(edges)
    if kind == "tuple":
        return tuple(edges)
    if kind == "generator":
        return generator_from(edges)
    raise ValueError(f"unknown input kind: {kind}")


def build_ctor(
    lib: Any,
    edges: list[Any],
    *,
    kind: str = "list",
    graph_attr: dict[str, Any] | None = None,
) -> Any:
    incoming = input_for_kind(kind, edges)
    if graph_attr is None:
        return lib.Graph(incoming)
    return lib.Graph(incoming, **graph_attr)


def apply_case(lib: Any, case: dict[str, Any]) -> dict[str, Any]:
    try:
        graph = build_ctor(
            lib,
            case["edges"],
            kind=case.get("kind", "list"),
            graph_attr=case.get("graph_attr"),
        )
    except Exception as exc:  # noqa: BLE001 - exception shape is part of parity.
        return {"error_type": type(exc).__name__, "error": str(exc)}

    result: dict[str, Any] = {"graph": canonical(graph)}
    if case.get("mutate_empty_edge_dict"):
        u, v, attrs = next(iter(graph.edges(data=True)))
        attrs["touched"] = True
        result["post_edge_data_mutation"] = list(graph.edges(data=True))[0][2]
        result["post_lookup"] = dict(graph[u][v])
    if case.get("mutate_attr_edge_dict"):
        u, v, attrs = next(iter(graph.edges(data=True)))
        attrs["extra"] = "live"
        result["post_attr_edge_mutation"] = list(graph.edges(data=True))[0][2]
        result["post_attr_lookup"] = dict(graph[u][v])
    return result


def proof_cases() -> list[dict[str, Any]]:
    attr = [
        (0, 1, {"w": 1, "label": "a"}),
        (1, 2, {"w": 2}),
        (0, 1, {"extra": True}),
        (3, 3, {"self": "loop"}),
    ]
    return [
        {
            "name": "plain_list",
            "kind": "list",
            "edges": [(0, 1), (1, 2), (2, 0), (2, 0), (3, 3)],
            "mutate_empty_edge_dict": True,
        },
        {
            "name": "plain_tuple_control",
            "kind": "tuple",
            "edges": [(0, 1), (1, 2), (2, 0), (2, 0), (3, 3)],
            "mutate_empty_edge_dict": True,
        },
        {
            "name": "plain_generator_control",
            "kind": "generator",
            "edges": [(0, 1), (1, 2), (2, 0), (2, 0), (3, 3)],
            "mutate_empty_edge_dict": True,
        },
        {
            "name": "attr_list",
            "kind": "list",
            "edges": attr,
            "mutate_attr_edge_dict": True,
        },
        {
            "name": "interleaved_slow_node",
            "kind": "list",
            "edges": [(0, 1), "sentinel", (2, 3, {"w": 3}), (3, 4)],
        },
        {
            "name": "bad_third_hashable",
            "kind": "list",
            "edges": [(0, 1), (9, 9, 9), (1, 2)],
        },
        {
            "name": "bad_str_item",
            "kind": "list",
            "edges": [(0, 1), "ab", (1, 2)],
        },
        {
            "name": "graph_attr",
            "kind": "list",
            "edges": [(0, 1), (1, 2)],
            "graph_attr": {"name": "ctor-list", "payload": [1, 2]},
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
        ("list_plain", plain_edges(), "list", 10),
        ("tuple_plain_control", plain_edges(), "tuple", 10),
        ("generator_plain_control", plain_edges(), "generator", 10),
        ("list_attr", attr_edges(), "list", 7),
    ]
    rows = []
    for name, edges, kind, loops in scenarios:
        fnx_stats = best_time(
            lambda edges=edges, kind=kind: build_ctor(fnx, edges, kind=kind), loops, 7
        )
        nx_stats = best_time(
            lambda edges=edges, kind=kind: build_ctor(nx, edges, kind=kind), loops, 7
        )
        rows.append(
            {
                "edges": len(edges),
                "fnx": fnx_stats,
                "fnx_vs_nx_best_ratio": fnx_stats["best_s"] / nx_stats["best_s"],
                "kind": kind,
                "name": name,
                "nx": nx_stats,
            }
        )
    print(json.dumps({"scenarios": rows}, indent=2, sort_keys=True))


def profile_body() -> None:
    plain = plain_edges()
    attributed = attr_edges()
    for _ in range(80):
        build_ctor(fnx, plain, kind="list")
        build_ctor(fnx, plain, kind="tuple")
        build_ctor(fnx, plain, kind="generator")
        build_ctor(fnx, attributed, kind="list")


def run_profile() -> None:
    profiler = cProfile.Profile()
    profiler.enable()
    profile_body()
    profiler.disable()
    stream = io.StringIO()
    pstats.Stats(profiler, stream=stream).sort_stats("cumtime").print_stats(50)
    print(stream.getvalue())


def run_fnx_loop(kind: str, case: str, loops: int) -> None:
    edges = attr_edges() if case == "attr" else plain_edges()
    total = 0
    for _ in range(loops):
        total += build_ctor(fnx, edges, kind=kind).number_of_edges()
    print(json.dumps({"case": case, "kind": kind, "loops": loops, "total_edges": total}))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["proof", "bench", "profile", "fnx-loop"])
    parser.add_argument("--case", choices=["plain", "attr"], default="plain")
    parser.add_argument("--kind", choices=["list", "tuple", "generator"], default="list")
    parser.add_argument("--loops", type=int, default=30)
    args = parser.parse_args()
    if args.mode == "proof":
        run_proof()
    elif args.mode == "bench":
        run_bench()
    elif args.mode == "profile":
        run_profile()
    else:
        run_fnx_loop(args.kind, args.case, args.loops)


if __name__ == "__main__":
    main()
