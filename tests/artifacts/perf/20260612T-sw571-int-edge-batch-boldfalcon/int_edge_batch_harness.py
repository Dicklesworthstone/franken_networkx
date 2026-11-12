#!/usr/bin/env python3
"""Focused evidence harness for br-r37-c1-sw571.

Targets ``empty_graph(n)`` followed by exact-int ``Graph.add_edges_from``.
The golden payload covers Python-visible order and fallback boundaries that the
index insertion fast path must preserve.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import statistics
import sys
import time
from pathlib import Path


def import_scratch_fnx_package():
    project_root = Path(os.environ.get("FNX_PROJECT_ROOT", Path(__file__).resolve().parents[4]))
    scratch_python = Path(os.environ.get("FNX_SCRATCH_PYTHON", project_root / "python"))
    default_so_path = scratch_python / "franken_networkx" / "_fnx.abi3.so"
    so_path = Path(os.environ.get("FNX_EXTENSION_SO", default_so_path))

    spec = importlib.util.spec_from_file_location("franken_networkx._fnx", so_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load franken_networkx._fnx from {so_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["franken_networkx._fnx"] = module
    spec.loader.exec_module(module)

    sys.path.insert(0, str(scratch_python))
    import franken_networkx as package

    package_file = Path(package.__file__).resolve()
    if not package_file.is_relative_to(scratch_python.resolve()):
        raise ImportError(f"franken_networkx resolved outside scratch package: {package_file}")
    if package._fnx is not module:
        raise ImportError("franken_networkx._fnx did not resolve to the preloaded extension")
    return package


fnx = import_scratch_fnx_package()


def make_edges(n: int, m: int) -> list[tuple[int, int]]:
    if n <= 1:
        return []
    max_edges = n * (n - 1) // 2
    if m > max_edges:
        raise ValueError(f"requested {m} unique simple edges for n={n}, max={max_edges}")
    edges: list[tuple[int, int]] = []
    seen: set[tuple[int, int]] = set()
    for offset in range(1, n):
        for u in range(n):
            v = (u + offset) % n
            key = (u, v) if u <= v else (v, u)
            if key in seen:
                continue
            seen.add(key)
            edges.append((u, v))
            if len(edges) == m:
                return edges
    return edges


def graph_digest(graph: fnx.Graph, *, label: str) -> dict[str, object]:
    nodes = list(graph.nodes())
    edges = list(graph.edges())
    adjacency = [(node, list(graph.adj[node])) for node in nodes]
    degrees = list(graph.degree())
    payload = {
        "label": label,
        "node_order": nodes,
        "edge_order": edges,
        "adjacency_row_order": adjacency,
        "degree_sequence": degrees,
        "node_count": graph.number_of_nodes(),
        "edge_count": graph.number_of_edges(),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=repr).encode()
    return {"sha256": hashlib.sha256(encoded).hexdigest(), "payload": payload}


def capture_partial_error() -> dict[str, object]:
    graph = fnx.empty_graph(4)
    try:
        graph.add_edges_from([(0, 1), (1, 2, 1.5), (2, 3)])
    except Exception as exc:  # noqa: BLE001 - golden captures public exception shape.
        return {
            "type": type(exc).__name__,
            "message": str(exc),
            "digest": graph_digest(graph, label="partial_error"),
        }
    raise AssertionError("expected non-dict third edge element to fail")


def capture_fallbacks() -> dict[str, object]:
    cases: dict[str, dict[str, object]] = {}

    bool_graph = fnx.empty_graph(3)
    bool_graph.add_edges_from([(True, 2), (False, 1)])
    cases["bool_endpoints"] = graph_digest(bool_graph, label="bool_endpoints")

    float_graph = fnx.empty_graph(3)
    float_graph.add_edges_from([(0.0, 1), (1.5, 2)])
    cases["float_endpoints"] = graph_digest(float_graph, label="float_endpoints")

    tuple_graph = fnx.empty_graph(2)
    tuple_graph.add_edges_from([((0, 0), 1), ((0, 1), 0)])
    cases["tuple_endpoints"] = graph_digest(tuple_graph, label="tuple_endpoints")

    missing_graph = fnx.empty_graph(3)
    missing_graph.add_edges_from([(0, 3), (3, 4)])
    cases["missing_nodes"] = graph_digest(missing_graph, label="missing_nodes")

    attr_graph = fnx.empty_graph(3)
    attr_graph.add_edges_from([(0, 1, {"weight": 7}), (1, 2)], color="red")
    cases["attrs"] = graph_digest(attr_graph, label="attrs")
    cases["attrs"]["edge_data"] = list(attr_graph.edges(data=True))

    generator_graph = fnx.empty_graph(4)
    generator_graph.add_edges_from((edge for edge in [(0, 1), (1, 2), (2, 3)]))
    cases["generator_input"] = graph_digest(generator_graph, label="generator_input")

    return cases


def capture_random_regular() -> dict[str, object]:
    graph = fnx.random_regular_graph(8, 1500, seed=12345)
    digest = graph_digest(graph, label="random_regular_graph")
    return {
        "sha256": digest["sha256"],
        "node_count": digest["payload"]["node_count"],
        "edge_count": digest["payload"]["edge_count"],
    }


def goldens(n: int, m: int) -> dict[str, object]:
    edges = make_edges(n, m)
    graph = fnx.empty_graph(n)
    graph.add_edges_from(edges)
    payload = {
        "target": "empty_graph_exact_int_add_edges_from",
        "n": n,
        "m": m,
        "main": graph_digest(graph, label="main"),
        "partial_error": capture_partial_error(),
        "fallbacks": capture_fallbacks(),
        "random_regular_graph": capture_random_regular(),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=repr).encode()
    return {"sha256": hashlib.sha256(encoded).hexdigest(), "payload": payload}


def bench_once_edges(n: int, edges: list[tuple[int, int]]) -> int:
    graph = fnx.empty_graph(n)
    graph.add_edges_from(edges)
    return graph.number_of_edges()


def loop_times(n: int, m: int, repeat: int) -> dict[str, object]:
    edges = make_edges(n, m)
    times: list[float] = []
    edge_count = 0
    for _ in range(repeat):
        start = time.perf_counter()
        edge_count += bench_once_edges(n, edges)
        times.append(time.perf_counter() - start)
    ordered = sorted(times)
    return {
        "n": n,
        "m": m,
        "repeat": repeat,
        "edge_count_accumulator": edge_count,
        "mean_s": statistics.fmean(times),
        "median_s": statistics.median(times),
        "p95_s": ordered[int((len(ordered) - 1) * 0.95)],
        "min_s": min(times),
        "max_s": max(times),
        "times_s": times,
    }


def profile_driver(n: int, m: int, repeat: int) -> None:
    edges = make_edges(n, m)
    for _ in range(repeat):
        bench_once_edges(n, edges)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["golden", "bench", "profile"], required=True)
    parser.add_argument("--n", type=int, default=1500)
    parser.add_argument("--m", type=int, default=12000)
    parser.add_argument("--repeat", type=int, default=25)
    args = parser.parse_args()

    if args.mode == "golden":
        print(json.dumps(goldens(args.n, args.m), sort_keys=True, indent=2, default=repr))
    elif args.mode == "bench":
        print(json.dumps(loop_times(args.n, args.m, args.repeat), sort_keys=True))
    else:
        profile_driver(args.n, args.m, args.repeat)


if __name__ == "__main__":
    main()
