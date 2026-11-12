#!/usr/bin/env python3
"""Benchmark and parity proof for br-r37-c1-edmwo."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from collections.abc import Callable
from typing import Any


CASES: dict[str, tuple[str, tuple[Any, ...], dict[str, Any]]] = {
    "grid_8_8_8": ("grid_graph", ([8, 8, 8],), {}),
    "hypercube_10": ("hypercube_graph", (10,), {}),
    "hypercube_13": ("hypercube_graph", (13,), {}),
}

PROOF_CASES: tuple[tuple[str, tuple[Any, ...], dict[str, Any]], ...] = (
    ("grid_graph", ([0, 3],), {}),
    ("grid_graph", ([1],), {}),
    ("grid_graph", ([2],), {}),
    ("grid_graph", ([2, 3],), {}),
    ("grid_graph", ([3, 2],), {}),
    ("grid_graph", ([2, 2, 2],), {}),
    ("grid_graph", ([3, 4, 2],), {}),
    ("grid_graph", ([2, 3],), {"periodic": True}),
    ("grid_graph", ([3, 4, 2],), {"periodic": [True, False, True]}),
    ("hypercube_graph", (0,), {}),
    ("hypercube_graph", (1,), {}),
    ("hypercube_graph", (2,), {}),
    ("hypercube_graph", (5,), {}),
)


def canonical(graph: Any) -> dict[str, Any]:
    return {
        "nodes": [repr(node) for node in graph.nodes()],
        "edges": [(repr(u), repr(v)) for u, v in graph.edges()],
        "adjacency": {
            repr(node): [repr(neighbor) for neighbor in graph[node]]
            for node in graph
        },
    }


def graph_size(graph: Any) -> tuple[int, int]:
    return graph.number_of_nodes(), graph.number_of_edges()


def load_impl(name: str) -> Any:
    if name == "fnx":
        import franken_networkx as graphlib
    elif name == "nx":
        import networkx as graphlib
    else:
        raise ValueError(f"unknown impl {name!r}")
    return graphlib


def bench(impl: str, case: str, repeat: int) -> None:
    graphlib = load_impl(impl)
    func_name, args, kwargs = CASES[case]
    func: Callable[..., Any] = getattr(graphlib, func_name)
    start = time.perf_counter()
    sizes = None
    for _ in range(repeat):
        graph = func(*args, **kwargs)
        sizes = graph_size(graph)
    elapsed = time.perf_counter() - start
    print(json.dumps({"impl": impl, "case": case, "repeat": repeat, "elapsed": elapsed, "size": sizes}))


def proof() -> None:
    import franken_networkx as fnx
    import networkx as nx

    records = []
    for func_name, args, kwargs in PROOF_CASES:
        fnx_graph = getattr(fnx, func_name)(*args, **kwargs)
        nx_graph = getattr(nx, func_name)(*args, **kwargs)
        fnx_canon = canonical(fnx_graph)
        nx_canon = canonical(nx_graph)
        if fnx_canon != nx_canon:
            raise AssertionError(
                json.dumps(
                    {
                        "func": func_name,
                        "args": repr(args),
                        "kwargs": kwargs,
                        "fnx": fnx_canon,
                        "nx": nx_canon,
                    },
                    sort_keys=True,
                )
            )
        records.append(
            {
                "func": func_name,
                "args": repr(args),
                "kwargs": kwargs,
                "canon": fnx_canon,
            }
        )
    payload = json.dumps(records, sort_keys=True, separators=(",", ":")).encode()
    print("GOLDEN_SHA256", hashlib.sha256(payload).hexdigest())
    print("CASES", len(records))


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    bench_parser = sub.add_parser("bench")
    bench_parser.add_argument("--impl", choices=("fnx", "nx"), required=True)
    bench_parser.add_argument("--case", choices=tuple(CASES), required=True)
    bench_parser.add_argument("--repeat", type=int, default=1)
    sub.add_parser("proof")
    args = parser.parse_args()
    if args.command == "bench":
        bench(args.impl, args.case, args.repeat)
    else:
        proof()


if __name__ == "__main__":
    main()
