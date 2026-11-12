#!/usr/bin/env python3
"""Tree distance benchmark for center/radius/periphery/diameter."""

from __future__ import annotations

import argparse
import gc
import hashlib
import json
import time
from typing import Any, Callable

import franken_networkx as fnx
import networkx as nx


def build_pair(n: int) -> tuple[Any, Any]:
    base = nx.path_graph(n)
    rust_graph = fnx.Graph()
    rust_graph.add_nodes_from(base.nodes())
    rust_graph.add_edges_from(base.edges())
    return rust_graph, base


def op_table() -> dict[str, Callable[[Any, Any], Any]]:
    return {
        "center": lambda mod, graph: mod.center(graph),
        "radius": lambda mod, graph: mod.radius(graph),
        "periphery": lambda mod, graph: mod.periphery(graph),
        "diameter": lambda mod, graph: mod.diameter(graph),
    }


def normalize(value: Any) -> Any:
    if isinstance(value, dict):
        return {repr(k): normalize(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [normalize(v) for v in value]
    return value


def sample(impl: str, op: str, repeat: int, n: int) -> dict[str, Any]:
    graph_f, graph_n = build_pair(n)
    graph = graph_f if impl == "fnx" else graph_n
    module = fnx if impl == "fnx" else nx
    ops = op_table()
    selected = ops if op == "all" else {op: ops[op]}
    outputs: list[Any] = []
    durations: list[float] = []

    gc.collect()
    gc.disable()
    try:
        for _ in range(repeat):
            start = time.perf_counter()
            result = {name: normalize(func(module, graph)) for name, func in selected.items()}
            durations.append(time.perf_counter() - start)
            outputs.append(result)
    finally:
        gc.enable()

    payload = json.dumps(outputs, sort_keys=True, separators=(",", ":")).encode()
    ordered = sorted(durations)
    return {
        "impl": impl,
        "op": op,
        "repeat": repeat,
        "n": n,
        "mean_seconds": sum(durations) / len(durations),
        "min_seconds": ordered[0],
        "p50_seconds": ordered[len(ordered) // 2],
        "max_seconds": ordered[-1],
        "sha256": hashlib.sha256(payload).hexdigest(),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--impl", choices=["fnx", "nx"], required=True)
    parser.add_argument("--op", choices=["center", "radius", "periphery", "diameter", "all"], default="center")
    parser.add_argument("--repeat", type=int, default=10)
    parser.add_argument("--n", type=int, default=1500)
    args = parser.parse_args()

    print(json.dumps(sample(args.impl, args.op, args.repeat, args.n), sort_keys=True))


if __name__ == "__main__":
    main()
