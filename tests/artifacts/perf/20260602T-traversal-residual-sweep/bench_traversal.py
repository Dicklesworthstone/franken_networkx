#!/usr/bin/env python3
"""Residual traversal/path profiler for the no-gaps campaign."""

from __future__ import annotations

import argparse
import gc
import hashlib
import json
import time
from typing import Any, Callable

import franken_networkx as fnx
import networkx as nx


def build_pair(n: int, m: int, seed: int) -> tuple[Any, Any]:
    generated = nx.barabasi_albert_graph(n, m, seed=seed)
    base = nx.Graph()
    base.add_nodes_from(generated.nodes())
    base.add_edges_from(generated.edges())
    rust_graph = fnx.Graph()
    rust_graph.add_nodes_from(base.nodes())
    rust_graph.add_edges_from(base.edges())
    return rust_graph, base


def op_table(target: int) -> dict[str, Callable[[Any, Any], Any]]:
    return {
        "single_source_shortest_path_length": lambda mod, g: mod.single_source_shortest_path_length(g, 0),
        "single_source_shortest_path": lambda mod, g: mod.single_source_shortest_path(g, 0),
        "shortest_path_length": lambda mod, g: mod.shortest_path_length(g, 0, target),
        "shortest_path": lambda mod, g: mod.shortest_path(g, 0, target),
        "bfs_edges": lambda mod, g: list(mod.bfs_edges(g, 0)),
        "dfs_edges": lambda mod, g: list(mod.dfs_edges(g, 0)),
        "bfs_tree": lambda mod, g: mod.bfs_tree(g, 0),
        "ego_graph_r2": lambda mod, g: mod.ego_graph(g, 0, radius=2),
    }


def normalize(value: Any) -> Any:
    if hasattr(value, "edges") and hasattr(value, "nodes"):
        return {
            "nodes": sorted(repr(node) for node in value.nodes()),
            "edges": sorted((repr(u), repr(v)) for u, v in value.edges()),
        }
    if isinstance(value, dict):
        return {repr(k): normalize(v) for k, v in sorted(value.items(), key=lambda item: repr(item[0]))}
    if isinstance(value, (list, tuple)):
        return [normalize(v) for v in value]
    return value


def sample(impl: str, op: str, repeat: int, n: int, m: int, seed: int) -> dict[str, Any]:
    graph_f, graph_n = build_pair(n, m, seed)
    graph = graph_f if impl == "fnx" else graph_n
    module = fnx if impl == "fnx" else nx
    func = op_table(n - 1)[op]
    outputs: list[Any] = []
    durations: list[float] = []

    gc.collect()
    gc.disable()
    try:
        for _ in range(repeat):
            start = time.perf_counter()
            out = func(module, graph)
            durations.append(time.perf_counter() - start)
            outputs.append(normalize(out))
    finally:
        gc.enable()

    payload = json.dumps(outputs, sort_keys=True, separators=(",", ":")).encode()
    ordered = sorted(durations)
    return {
        "impl": impl,
        "op": op,
        "repeat": repeat,
        "n": n,
        "m": m,
        "graph_seed": seed,
        "mean_seconds": sum(durations) / len(durations),
        "min_seconds": ordered[0],
        "p50_seconds": ordered[len(ordered) // 2],
        "max_seconds": ordered[-1],
        "sha256": hashlib.sha256(payload).hexdigest(),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["sample", "sweep"])
    parser.add_argument("--impl", choices=["fnx", "nx"], default="fnx")
    parser.add_argument("--op", choices=tuple(op_table(1).keys()), default="bfs_edges")
    parser.add_argument("--repeat", type=int, default=5)
    parser.add_argument("--n", type=int, default=3000)
    parser.add_argument("--m", type=int, default=4)
    parser.add_argument("--graph-seed", type=int, default=42)
    args = parser.parse_args()

    if args.mode == "sweep":
        for op in op_table(args.n - 1):
            for impl in ("fnx", "nx"):
                print(
                    json.dumps(
                        sample(impl, op, args.repeat, args.n, args.m, args.graph_seed),
                        sort_keys=True,
                    )
                )
    else:
        print(
            json.dumps(
                sample(args.impl, args.op, args.repeat, args.n, args.m, args.graph_seed),
                sort_keys=True,
            )
        )


if __name__ == "__main__":
    main()
