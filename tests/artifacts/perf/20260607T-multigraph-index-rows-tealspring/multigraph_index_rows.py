#!/usr/bin/env python3
"""Bench/proof harness for MultiGraph index-row storage."""

from __future__ import annotations

import argparse
import cProfile
import hashlib
import io
import json
import pickle
import pstats
import random
import statistics
import time
from collections.abc import Callable
from typing import Any

import franken_networkx as fnx
import networkx as nx


def plain_edges(n: int = 5000, m: int = 14000, seed: int = 173) -> list[tuple[int, int]]:
    rng = random.Random(seed)
    edges = [(i, i + 1) for i in range(n - 1)]
    while len(edges) < m:
        u = rng.randrange(n)
        v = rng.randrange(n)
        edges.append((u, v))
    return edges


def keyed_edges(n: int = 5000, m: int = 14000) -> list[tuple[int, int, str]]:
    return [(i % n, (i * 17 + 7) % n, f"k{i}") for i in range(m)]


def attr_edges(n: int = 4000, m: int = 10000) -> list[tuple[int, int, str, dict[str, Any]]]:
    return [
        (
            i % n,
            (i * 19 + 11) % n,
            f"k{i}",
            {"weight": i % 997, "label": f"{i}->{(i * 19 + 11) % n}"},
        )
        for i in range(m)
    ]


def token(value: Any) -> str:
    return f"{type(value).__name__}:{value!r}"


def canonical(graph: Any, limit: int | None = None) -> dict[str, Any]:
    edges = list(graph.edges(keys=True, data=True))
    if limit is not None:
        edges = edges[:limit]
    return {
        "nodes": [token(node) for node in graph.nodes()],
        "neighbors": {token(node): [token(nbr) for nbr in graph.neighbors(node)] for node in graph.nodes()},
        "edges": [
            [token(u), token(v), token(key), sorted((str(k), repr(vv)) for k, vv in attrs.items())]
            for u, v, key, attrs in edges
        ],
        "graph": sorted((str(k), repr(v)) for k, v in graph.graph.items()),
    }


def build_ctor(module: Any, case: str) -> Any:
    if case == "plain":
        return module.MultiGraph(plain_edges())
    if case == "keyed":
        return module.MultiGraph(keyed_edges())
    if case == "attr":
        return module.MultiGraph(attr_edges(), name="attr-case")
    raise ValueError(case)


def build_add_loop(module: Any, case: str) -> Any:
    graph = module.MultiGraph()
    if case == "plain":
        for u, v in plain_edges():
            graph.add_edge(u, v)
    elif case == "keyed":
        for u, v, key in keyed_edges():
            graph.add_edge(u, v, key=key)
    elif case == "attr":
        for u, v, key, attrs in attr_edges():
            graph.add_edge(u, v, key=key, **attrs)
    else:
        raise ValueError(case)
    return graph


def proof_surface(module: Any) -> dict[str, Any]:
    graph = module.MultiGraph(name="proof")
    graph.add_edge(0, 1, key="first", weight=1)
    graph.add_edge("s", "s", key=3, loop=True)
    graph.add_edge(0, 1, key="first", color="red")
    graph[0][1]["first"]["live"] = True
    ctor = module.MultiGraph([(0, 1, "a"), (1, 2, "b"), (1, 2, "c", {"w": 3})])
    copied = graph.copy()
    payload = pickle.dumps(graph)
    # The payload is generated locally above; pickle parity is part of graph behavior.
    restored = pickle.Unpickler(io.BytesIO(payload)).load()  # nosec B301
    graph.remove_node("s")
    return {
        "base": canonical(graph),
        "ctor": canonical(ctor),
        "copy": canonical(copied),
        "pickle": canonical(restored),
        "edge_data": {token(k): dict(v) for k, v in copied.get_edge_data(0, 1).items()},
        "auto_keys": list(module.MultiGraph([(0, 1), (0, 1), (0, 1)]).edges(keys=True)),
    }


def display_conflict_surface(module: Any) -> dict[str, Any]:
    graph = module.MultiGraph()
    graph.add_edge(1.0, True, key="equal", label="mixed-display")
    return canonical(graph)


def run_proof() -> None:
    fnx_surface = proof_surface(fnx)
    nx_surface = proof_surface(nx)
    fnx_display_conflict = display_conflict_surface(fnx)
    nx_display_conflict = display_conflict_surface(nx)
    payload = {
        "matches_nx": fnx_surface == nx_surface,
        "core_fnx": fnx_surface,
        "core_nx": nx_surface,
        "display_conflict_matches_nx": fnx_display_conflict == nx_display_conflict,
        "display_conflict_fnx_current": fnx_display_conflict,
        "display_conflict_nx": nx_display_conflict,
        "ordering_tie_breaking": "node order, neighbor row order, edge key order, copy/pickle order included",
        "floating_point": "no FP algorithm output; numeric/bool hash-equal display conflict tracked as current behavior",
        "rng": "seeded construction fixture only",
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    print(json.dumps({"golden_sha256": hashlib.sha256(encoded).hexdigest(), **payload}, sort_keys=True))


def best_time(func: Callable[[], Any], loops: int, samples: int) -> dict[str, float]:
    times = []
    for _ in range(samples):
        start = time.perf_counter()
        for _ in range(loops):
            graph = func()
            if graph.number_of_edges() == 0:
                raise AssertionError("empty graph")
        times.append((time.perf_counter() - start) / loops)
    return {"best_s": min(times), "mean_s": statistics.fmean(times), "median_s": statistics.median(times)}


def run_bench() -> None:
    rows = []
    for mode in ("ctor", "add_loop"):
        for case, loops in (("plain", 6), ("keyed", 6), ("attr", 4)):
            builder = build_ctor if mode == "ctor" else build_add_loop
            fnx_stats = best_time(lambda builder=builder, case=case: builder(fnx, case), loops, 7)
            nx_stats = best_time(lambda builder=builder, case=case: builder(nx, case), loops, 7)
            rows.append(
                {
                    "case": case,
                    "mode": mode,
                    "fnx": fnx_stats,
                    "nx": nx_stats,
                    "fnx_over_nx_best": fnx_stats["best_s"] / nx_stats["best_s"],
                }
            )
    print(json.dumps({"scenarios": rows}, indent=2, sort_keys=True))


def run_profile() -> None:
    profiler = cProfile.Profile()
    profiler.enable()
    for _ in range(20):
        build_ctor(fnx, "plain")
        build_ctor(fnx, "keyed")
        build_ctor(fnx, "attr")
        build_add_loop(fnx, "keyed")
    profiler.disable()
    stream = io.StringIO()
    pstats.Stats(profiler, stream=stream).sort_stats("cumtime").print_stats(60)
    print(stream.getvalue())


def run_fnx_loop(mode: str, case: str, loops: int) -> None:
    builder = build_ctor if mode == "ctor" else build_add_loop
    total = 0
    for _ in range(loops):
        total += builder(fnx, case).number_of_edges()
    print(json.dumps({"case": case, "loops": loops, "mode": mode, "total": total}))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["proof", "bench", "profile", "fnx-loop"])
    parser.add_argument("--mode", choices=["ctor", "add_loop"], default="ctor")
    parser.add_argument("--case", choices=["plain", "keyed", "attr"], default="plain")
    parser.add_argument("--loops", type=int, default=12)
    args = parser.parse_args()
    if args.command == "proof":
        run_proof()
    elif args.command == "bench":
        run_bench()
    elif args.command == "profile":
        run_profile()
    else:
        run_fnx_loop(args.mode, args.case, args.loops)


if __name__ == "__main__":
    main()
