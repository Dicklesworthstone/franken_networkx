#!/usr/bin/env python3
"""Perf/golden harness for br-r37-c1-dxm71."""

from __future__ import annotations

import argparse
import cProfile
import gc
import hashlib
import io
import json
import pstats
import random
import time
from typing import Any

import franken_networkx as fnx
import networkx as nx


def build_pair(n: int, m: int, seed: int) -> tuple[Any, Any]:
    base = nx.barabasi_albert_graph(n, m, seed=seed)
    rust_graph = fnx.Graph()
    rust_graph.add_nodes_from(base.nodes())
    rust_graph.add_edges_from(base.edges())
    return rust_graph, base


def call_mis(impl: str, graph: Any, seed: Any, nodes: list[int] | None = None) -> Any:
    module = fnx if impl == "fnx" else nx
    if seed is None:
        random.seed(1_357_911)
    if nodes is None:
        return module.maximal_independent_set(graph, seed=seed)
    return module.maximal_independent_set(graph, nodes=nodes, seed=seed)


def normalized_call(
    impl: str, graph: Any, seed: Any, nodes: list[int] | None = None
) -> dict[str, Any]:
    try:
        return {"ok": True, "value": list(call_mis(impl, graph, seed, nodes))}
    except Exception as exc:  # noqa: BLE001 - golden records observable error class/message.
        return {
            "ok": False,
            "class": type(exc).__name__,
            "message": str(exc),
        }


def golden_payload() -> dict[str, Any]:
    cases: list[dict[str, Any]] = []
    graphs: list[tuple[str, Any, Any]] = []

    path_f = fnx.path_graph(24)
    path_n = nx.path_graph(24)
    graphs.append(("path24", path_f, path_n))

    cycle_n = nx.cycle_graph(31)
    cycle_f = fnx.Graph()
    cycle_f.add_nodes_from(cycle_n.nodes())
    cycle_f.add_edges_from(cycle_n.edges())
    graphs.append(("cycle31", cycle_f, cycle_n))

    ba_f, ba_n = build_pair(120, 3, 42)
    graphs.append(("ba120_3", ba_f, ba_n))

    self_f = fnx.Graph()
    self_f.add_edge(0, 0)
    self_n = nx.Graph()
    self_n.add_edge(0, 0)
    graphs.append(("selfloop", self_f, self_n))

    for name, graph_f, graph_n in graphs:
        for seed in [None, 0, 1, 7, 2**31 + 17]:
            for nodes in [None, [0]]:
                cases.append(
                    {
                        "case": name,
                        "seed": seed,
                        "nodes": nodes,
                        "fnx": normalized_call("fnx", graph_f, seed, nodes),
                        "nx": normalized_call("nx", graph_n, seed, nodes),
                    }
                )

    payload = json.dumps(cases, sort_keys=True, separators=(",", ":")).encode()
    return {"sha256": hashlib.sha256(payload).hexdigest(), "cases": cases}


def sample(impl: str, repeat: int, n: int, m: int, seed: int, call_seed: int) -> dict[str, Any]:
    graph_f, graph_n = build_pair(n, m, seed)
    graph = graph_f if impl == "fnx" else graph_n

    gc.collect()
    gc.disable()
    try:
        durations: list[float] = []
        outputs: list[list[Any]] = []
        for _ in range(repeat):
            start = time.perf_counter()
            out = call_mis(impl, graph, call_seed)
            durations.append(time.perf_counter() - start)
            outputs.append(list(out))
    finally:
        gc.enable()

    payload = json.dumps(outputs, sort_keys=True, separators=(",", ":")).encode()
    durations_sorted = sorted(durations)
    return {
        "impl": impl,
        "repeat": repeat,
        "n": n,
        "m": m,
        "graph_seed": seed,
        "call_seed": call_seed,
        "mean_seconds": sum(durations) / len(durations),
        "min_seconds": durations_sorted[0],
        "p50_seconds": durations_sorted[len(durations_sorted) // 2],
        "max_seconds": durations_sorted[-1],
        "sha256": hashlib.sha256(payload).hexdigest(),
    }


def profile(impl: str, repeat: int, n: int, m: int, seed: int, call_seed: int) -> str:
    profiler = cProfile.Profile()
    profiler.enable()
    sample(impl, repeat, n, m, seed, call_seed)
    profiler.disable()
    stream = io.StringIO()
    pstats.Stats(profiler, stream=stream).sort_stats("cumulative").print_stats(30)
    return stream.getvalue()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["sample", "golden", "profile"])
    parser.add_argument("--impl", choices=["fnx", "nx"], default="fnx")
    parser.add_argument("--repeat", type=int, default=30)
    parser.add_argument("--n", type=int, default=3000)
    parser.add_argument("--m", type=int, default=3)
    parser.add_argument("--graph-seed", type=int, default=42)
    parser.add_argument("--call-seed", type=int, default=7)
    args = parser.parse_args()

    if args.mode == "golden":
        print(json.dumps(golden_payload(), sort_keys=True))
    elif args.mode == "profile":
        print(profile(args.impl, args.repeat, args.n, args.m, args.graph_seed, args.call_seed))
    else:
        print(
            json.dumps(
                sample(args.impl, args.repeat, args.n, args.m, args.graph_seed, args.call_seed),
                sort_keys=True,
            )
        )


if __name__ == "__main__":
    main()
