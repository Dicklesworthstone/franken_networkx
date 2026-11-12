#!/usr/bin/env python3
"""Proof and benchmark harness for br-r37-c1-p34di."""

from __future__ import annotations

import argparse
import cProfile
import hashlib
import io
import json
import pstats
import statistics
import time
from typing import Any, Callable

import franken_networkx as fnx
import networkx as nx


def canonical(value: Any) -> dict[str, str]:
    return {"repr": repr(value), "type": type(value).__name__}


def build_hub_graph(module: Any, degree: int) -> Any:
    graph = module.Graph()
    graph.add_node(0, role="hub")
    graph.add_edges_from(
        (0, i, {"weight": i % 17, "tag": f"n{i % 5}"}) for i in range(1, degree + 1)
    )
    return graph


def build_mixed_graph(module: Any) -> Any:
    graph = module.Graph()
    graph.add_node(0, role="int-zero")
    graph.add_node(0.0, seen="float-zero")
    graph.add_node(True, seen="true")
    graph.add_node("0", role="string-zero")
    graph.add_edge(0, "0", weight=7)
    graph.add_edge(0.0, 2, weight=11)
    graph.add_edge(True, 3, weight=13)
    graph.add_edge("0", 4, weight=17)
    return graph


def row_semantics(graph: Any, node: Any) -> dict[str, Any]:
    row = graph[node]
    adj_row = graph.adj[node]
    row_items = [(canonical(k), sorted(v.items())) for k, v in row.items()]
    before = dict(row)
    first_neighbor = next(iter(row))
    row[first_neighbor]["marker"] = "live"
    live_visible = graph[node][first_neighbor]["marker"]
    del graph[node][first_neighbor]["marker"]
    return {
        "row_keys": [canonical(k) for k in row],
        "adj_row_keys": [canonical(k) for k in adj_row],
        "row_items": row_items,
        "copy_items": [(canonical(k), sorted(v.items())) for k, v in row.copy().items()],
        "dict_keys": [canonical(k) for k in before],
        "live_attr_alias": live_visible,
        "contains_first": first_neighbor in row,
        "missing_default": row.get("__missing__", "fallback"),
    }


def mutation_error_text(module: Any, action: Callable[[Any], None]) -> str:
    graph = module.Graph()
    graph.add_edges_from([(0, 1), (0, 2), (0, 3)])
    iterator = iter(graph[0])
    first = next(iterator)
    try:
        action(graph)
        next(iterator)
    except RuntimeError as exc:
        return f"{canonical(first)}|{type(exc).__name__}|{str(exc)}"
    except Exception as exc:  # capture mismatched exception classes in proof payload
        return f"{canonical(first)}|{type(exc).__name__}|{str(exc)}"
    return f"{canonical(first)}|NO_ERROR"


def semantic_payload(module: Any) -> dict[str, Any]:
    mixed = build_mixed_graph(module)
    hub = build_hub_graph(module, 8)
    return {
        "mixed_nodes": [canonical(node) for node in mixed.nodes],
        "mixed_edges": [[canonical(item) for item in edge] for edge in mixed.edges],
        "mixed_row_zero": row_semantics(mixed, 0),
        "hub_row": row_semantics(hub, 0),
        "adj_outer_keys": [canonical(node) for node in hub.adj],
        "neighbors_zero": [canonical(node) for node in hub.neighbors(0)],
        "row_size_error": mutation_error_text(module, lambda g: g.add_edge(0, 4)),
        "row_keys_error": mutation_error_text(
            module, lambda g: (g.remove_edge(0, 3), g.add_edge(0, 4))
        ),
        "row_clear_error": mutation_error_text(module, lambda g: g.clear()),
    }


def iterator_type_payload(module: Any) -> dict[str, str]:
    graph = build_hub_graph(module, 4)
    return {
        "adj_iter": type(iter(graph.adj)).__name__,
        "adj_row_iter": type(iter(graph.adj[0])).__name__,
        "getitem_row_iter": type(iter(graph[0])).__name__,
        "neighbors": type(graph.neighbors(0)).__name__,
    }


def emit_proof() -> None:
    fnx_semantic = semantic_payload(fnx)
    nx_semantic = semantic_payload(nx)
    semantic_match = fnx_semantic == nx_semantic
    raw = json.dumps(fnx_semantic, sort_keys=True, separators=(",", ":")).encode()
    payload = {
        "fnx_semantic_sha256": hashlib.sha256(raw).hexdigest(),
        "semantic_match_networkx": semantic_match,
        "fnx_iterator_types": iterator_type_payload(fnx),
        "nx_iterator_types": iterator_type_payload(nx),
        "fnx_semantic": fnx_semantic,
        "nx_semantic": nx_semantic,
    }
    print(json.dumps(payload, sort_keys=True, indent=2))


def time_case(label: str, func: Callable[[], int], repeat: int) -> dict[str, Any]:
    samples = []
    checksum = 0
    for _ in range(repeat):
        start = time.perf_counter()
        checksum += func()
        samples.append(time.perf_counter() - start)
    return {
        "case": label,
        "checksum": checksum,
        "mean_s": statistics.mean(samples),
        "median_s": statistics.median(samples),
        "min_s": min(samples),
        "repeat": repeat,
        "samples_s": samples,
    }


def emit_bench(degree: int, repeat: int) -> None:
    graph = build_hub_graph(fnx, degree)

    def getitem_row_list() -> int:
        return len(list(graph[0]))

    def adj_row_list() -> int:
        return len(list(graph.adj[0]))

    def neighbors_list() -> int:
        return len(list(graph.neighbors(0)))

    def adj_outer_list() -> int:
        return len(list(graph.adj))

    def row_items() -> int:
        total = 0
        for _node, attrs in graph[0].items():
            total += attrs.get("weight", 0)
        return total

    print(
        json.dumps(
            {
                "degree": degree,
                "repeat": repeat,
                "cases": [
                    time_case("getitem_row_list", getitem_row_list, repeat),
                    time_case("adj_row_list", adj_row_list, repeat),
                    time_case("neighbors_list", neighbors_list, repeat),
                    time_case("adj_outer_list", adj_outer_list, repeat),
                    time_case("row_items", row_items, repeat),
                ],
            },
            sort_keys=True,
            indent=2,
        )
    )


def run_loop(case: str, degree: int, loops: int) -> None:
    graph = build_hub_graph(fnx, degree)
    checksum = 0
    if case == "getitem_row_list":
        for _ in range(loops):
            checksum += len(list(graph[0]))
    elif case == "adj_row_list":
        for _ in range(loops):
            checksum += len(list(graph.adj[0]))
    elif case == "neighbors_list":
        for _ in range(loops):
            checksum += len(list(graph.neighbors(0)))
    elif case == "adj_outer_list":
        for _ in range(loops):
            checksum += len(list(graph.adj))
    elif case == "row_items":
        for _ in range(loops):
            for _node, attrs in graph[0].items():
                checksum += attrs.get("weight", 0)
    else:
        raise ValueError(f"unknown case: {case}")
    print(checksum)


def emit_profile(case: str, degree: int, loops: int) -> None:
    profiler = cProfile.Profile()
    profiler.enable()
    run_loop(case, degree, loops)
    profiler.disable()
    stream = io.StringIO()
    pstats.Stats(profiler, stream=stream).strip_dirs().sort_stats("tottime").print_stats(30)
    print(stream.getvalue())


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("proof", "bench", "loop", "profile"))
    parser.add_argument(
        "--case",
        choices=(
            "getitem_row_list",
            "adj_row_list",
            "neighbors_list",
            "adj_outer_list",
            "row_items",
        ),
        default="getitem_row_list",
    )
    parser.add_argument("--degree", type=int, default=20_000)
    parser.add_argument("--repeat", type=int, default=15)
    parser.add_argument("--loops", type=int, default=50)
    args = parser.parse_args()
    if args.mode == "proof":
        emit_proof()
    elif args.mode == "bench":
        emit_bench(args.degree, args.repeat)
    elif args.mode == "loop":
        run_loop(args.case, args.degree, args.loops)
    elif args.mode == "profile":
        emit_profile(args.case, args.degree, args.loops)


if __name__ == "__main__":
    main()
