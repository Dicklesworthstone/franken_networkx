#!/usr/bin/env python3
"""Bench/proof harness for MultiGraph/MultiDiGraph constructor batching."""

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


def mixed_edges(n: int = 5000, m: int = 14000, seed: int = 271) -> list[tuple[int, int, str, dict[str, Any]]]:
    rng = random.Random(seed)
    edges: list[tuple[int, int, str, dict[str, Any]]] = []
    for i in range(m):
        u = rng.randrange(n)
        v = rng.randrange(n)
        key = f"k{i % 7}" if i % 11 == 0 else f"k{i}"
        edges.append((u, v, key, {"weight": i % 211, "seen": i}))
    return edges


def token(value: Any) -> str:
    return f"{type(value).__name__}:{value!r}"


def directed_methods(graph: Any) -> tuple[Callable[[Any], Any], Callable[[Any], Any]]:
    if graph.is_directed():
        return graph.successors, graph.predecessors
    return graph.neighbors, graph.neighbors


def canonical(graph: Any, limit: int | None = None) -> dict[str, Any]:
    edges = list(graph.edges(keys=True, data=True))
    if limit is not None:
        edges = edges[:limit]
    succ_fn, pred_fn = directed_methods(graph)
    return {
        "nodes": [token(node) for node in graph.nodes()],
        "succ": {token(node): [token(nbr) for nbr in succ_fn(node)] for node in graph.nodes()},
        "pred": {token(node): [token(nbr) for nbr in pred_fn(node)] for node in graph.nodes()},
        "edges": [
            [token(u), token(v), token(key), sorted((str(k), repr(vv)) for k, vv in attrs.items())]
            for u, v, key, attrs in edges
        ],
        "graph": sorted((str(k), repr(v)) for k, v in graph.graph.items()),
    }


def graph_class(module: Any, kind: str) -> type:
    if kind == "multi":
        return module.MultiGraph
    if kind == "multidirected":
        return module.MultiDiGraph
    raise ValueError(kind)


def build_ctor(module: Any, kind: str, case: str) -> Any:
    cls = graph_class(module, kind)
    if case == "keyed":
        return cls(keyed_edges())
    if case == "attr":
        return cls(attr_edges(), name=f"{kind}-attr")
    if case == "mixed":
        return cls(mixed_edges(), name=f"{kind}-mixed")
    raise ValueError(case)


def build_add_loop(module: Any, kind: str, case: str) -> Any:
    graph = graph_class(module, kind)()
    if case == "keyed":
        for u, v, key in keyed_edges():
            graph.add_edge(u, v, key=key)
    elif case == "attr":
        for u, v, key, attrs in attr_edges():
            graph.add_edge(u, v, key=key, **attrs)
    elif case == "mixed":
        for u, v, key, attrs in mixed_edges():
            graph.add_edge(u, v, key=key, **attrs)
    else:
        raise ValueError(case)
    return graph


def proof_surface(module: Any, kind: str) -> dict[str, Any]:
    cls = graph_class(module, kind)
    graph = cls(name=f"{kind}-proof")
    graph.add_edge(0, 1, key="first", weight=1)
    graph.add_edge("s", "s", key=3, loop=True)
    graph.add_edge(0, 1, key="first", color="red")
    graph[0][1]["first"]["live"] = True
    ctor = cls(
        [
            (0, 1, "a"),
            (1, 2, "b"),
            (1, 2, "c", {"w": 3}),
            (1, 2, "c", {"w2": 4}),
            ("s", "s", 0, {"loop": True}),
        ],
        name=f"{kind}-ctor",
    )
    copied = graph.copy()
    payload = pickle.dumps(graph)
    restored = pickle.Unpickler(io.BytesIO(payload)).load()  # nosec B301
    graph.remove_node("s")
    return {
        "base": canonical(graph),
        "ctor": canonical(ctor),
        "copy": canonical(copied),
        "pickle": canonical(restored),
        "edge_data": {token(k): dict(v) for k, v in copied.get_edge_data(0, 1).items()},
        "auto_keys": list(cls([(0, 1), (0, 1), (0, 1)]).edges(keys=True)),
    }


def display_conflict_surface(module: Any, kind: str) -> dict[str, Any]:
    graph = graph_class(module, kind)()
    graph.add_edge(1.0, True, key="equal", label="mixed-display")
    return canonical(graph)


def exact_int_str_ctor_surface(module: Any, kind: str) -> dict[str, Any]:
    cls = graph_class(module, kind)
    graph = cls(
        [
            (0, 1, "a"),
            (1, 2, "b", {"weight": 3}),
            (1, 2, "b", {"color": "red"}),
            (2, 0, "c", {"payload": "triangle"}),
            (3, 3, "loop", {"loop": True}),
        ],
        name=f"{kind}-exact-int-str",
    )
    return canonical(graph)


def run_proof() -> None:
    surfaces: dict[str, Any] = {}
    for kind in ("multi", "multidirected"):
        fnx_surface = proof_surface(fnx, kind)
        nx_surface = proof_surface(nx, kind)
        fnx_display_conflict = display_conflict_surface(fnx, kind)
        nx_display_conflict = display_conflict_surface(nx, kind)
        fnx_exact_int_str = exact_int_str_ctor_surface(fnx, kind)
        nx_exact_int_str = exact_int_str_ctor_surface(nx, kind)
        surfaces[kind] = {
            "matches_nx": fnx_surface == nx_surface,
            "core_fnx": fnx_surface,
            "core_nx": nx_surface,
            "exact_int_str_ctor_matches_nx": fnx_exact_int_str == nx_exact_int_str,
            "exact_int_str_ctor_fnx": fnx_exact_int_str,
            "exact_int_str_ctor_nx": nx_exact_int_str,
            "display_conflict_matches_nx": fnx_display_conflict == nx_display_conflict,
            "display_conflict_fnx_current": fnx_display_conflict,
            "display_conflict_nx": nx_display_conflict,
        }
    payload = {
        "surfaces": surfaces,
        "ordering_tie_breaking": "node order, neighbor/successor/predecessor row order, edge key order, duplicate-key update order, copy/pickle order included",
        "floating_point": "no FP algorithm output; numeric/bool hash-equal display conflict tracked as current behavior",
        "rng": "seeded construction fixture only; no algorithmic RNG output",
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
    for kind in ("multi", "multidirected"):
        for mode in ("ctor", "add_loop"):
            for case, loops in (("keyed", 6), ("attr", 4), ("mixed", 4)):
                builder = build_ctor if mode == "ctor" else build_add_loop
                fnx_stats = best_time(lambda builder=builder, kind=kind, case=case: builder(fnx, kind, case), loops, 7)
                nx_stats = best_time(lambda builder=builder, kind=kind, case=case: builder(nx, kind, case), loops, 7)
                rows.append(
                    {
                        "case": case,
                        "kind": kind,
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
        for kind in ("multi", "multidirected"):
            build_ctor(fnx, kind, "keyed")
            build_ctor(fnx, kind, "attr")
            build_ctor(fnx, kind, "mixed")
            build_add_loop(fnx, kind, "keyed")
    profiler.disable()
    stream = io.StringIO()
    pstats.Stats(profiler, stream=stream).sort_stats("cumtime").print_stats(80)
    print(stream.getvalue())


def run_fnx_loop(kind: str, mode: str, case: str, loops: int) -> None:
    builder = build_ctor if mode == "ctor" else build_add_loop
    total = 0
    for _ in range(loops):
        total += builder(fnx, kind, case).number_of_edges()
    print(json.dumps({"case": case, "kind": kind, "loops": loops, "mode": mode, "total": total}))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["proof", "bench", "profile", "fnx-loop"])
    parser.add_argument("--kind", choices=["multi", "multidirected"], default="multi")
    parser.add_argument("--mode", choices=["ctor", "add_loop"], default="ctor")
    parser.add_argument("--case", choices=["keyed", "attr", "mixed"], default="keyed")
    parser.add_argument("--loops", type=int, default=12)
    args = parser.parse_args()
    if args.command == "proof":
        run_proof()
    elif args.command == "bench":
        run_bench()
    elif args.command == "profile":
        run_profile()
    else:
        run_fnx_loop(args.kind, args.mode, args.case, args.loops)


if __name__ == "__main__":
    main()
