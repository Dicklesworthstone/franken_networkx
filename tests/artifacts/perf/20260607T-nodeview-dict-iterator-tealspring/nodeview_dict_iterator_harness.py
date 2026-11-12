#!/usr/bin/env python3
"""Proof and benchmark harness for br-r37-c1-lni93."""

from __future__ import annotations

import argparse
import cProfile
import hashlib
import io
import json
import pstats
import statistics
import time
from collections.abc import Callable
from typing import Any

import franken_networkx as fnx


def build_graph(module: Any, n: int) -> Any:
    graph = module.Graph()
    graph.add_nodes_from(range(n))
    return graph


def canonical(value: Any) -> dict[str, str]:
    return {"type": type(value).__name__, "repr": repr(value)}


def runtime_error_text(action: Callable[[Any], None]) -> str:
    graph = fnx.Graph()
    graph.add_nodes_from([0, 1])
    iterator = iter(graph.nodes)
    first = next(iterator)
    try:
        action(graph)
        next(iterator)
    except RuntimeError as exc:
        return f"{canonical(first)}|{type(exc).__name__}|{str(exc)}"
    raise AssertionError("iterator mutation did not raise")


def proof_payload() -> dict[str, Any]:
    graph = fnx.Graph()
    graph.add_node(0, label="zero")
    graph.add_node(0.0, label="float-zero")
    graph.add_node(True, label="true")
    graph.add_node("0", label="string-zero")
    graph.add_edge(0, "0", weight=7)
    data_graph = fnx.Graph()
    data_graph.add_node("a", color="red")
    data_graph.add_node("b")
    return {
        "mixed_node_order": [canonical(node) for node in graph.nodes],
        "mixed_node_count": graph.number_of_nodes(),
        "mixed_edges": [[canonical(item) for item in edge] for edge in graph.edges],
        "nodes_data": [
            [canonical(node), sorted(attrs.items())]
            for node, attrs in data_graph.nodes(data=True)
        ],
        "nodes_attr_default": [
            [canonical(node), value]
            for node, value in data_graph.nodes(data="color", default="missing")
        ],
        "mutation_size_error": runtime_error_text(lambda g: g.add_node(2)),
        "mutation_keys_error": runtime_error_text(
            lambda g: (g.remove_node(1), g.add_node(2))
        ),
        "clear_error": runtime_error_text(lambda g: g.clear()),
        "add_edge_new_node_error": runtime_error_text(lambda g: g.add_edge(2, 0)),
        "existing_edge_no_error": list_existing_edge_mutation(),
        "nodes_seq": getattr(graph, "nodes_seq", None),
        "edges_seq": getattr(graph, "edges_seq", None),
    }


def list_existing_edge_mutation() -> list[dict[str, str]]:
    graph = fnx.Graph()
    graph.add_nodes_from([0, 1, 2])
    iterator = iter(graph.nodes)
    first = next(iterator)
    graph.add_edge(0, 1)
    rest = list(iterator)
    return [canonical(first), *[canonical(node) for node in rest]]


def emit_proof() -> None:
    payload = proof_payload()
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    print(
        json.dumps(
            {
                "sha256": hashlib.sha256(raw).hexdigest(),
                "payload": payload,
            },
            sort_keys=True,
            indent=2,
        )
    )


def time_case(label: str, func: Callable[[], int], repeat: int) -> dict[str, Any]:
    samples = []
    total = 0
    for _ in range(repeat):
        start = time.perf_counter()
        total += func()
        samples.append(time.perf_counter() - start)
    return {
        "case": label,
        "checksum": total,
        "repeat": repeat,
        "min_s": min(samples),
        "median_s": statistics.median(samples),
        "mean_s": statistics.mean(samples),
        "samples_s": samples,
    }


def emit_bench(n: int, repeat: int) -> None:
    graph = build_graph(fnx, n)

    def list_nodes() -> int:
        return len(list(graph.nodes))

    def consume_nodes() -> int:
        count = 0
        for _node in graph.nodes:
            count += 1
        return count

    print(
        json.dumps(
            {
                "n": n,
                "repeat": repeat,
                "cases": [
                    time_case("list_graph_nodes", list_nodes, repeat),
                    time_case("consume_graph_nodes", consume_nodes, repeat),
                ],
            },
            sort_keys=True,
            indent=2,
        )
    )


def run_loop(case: str, n: int, loops: int) -> None:
    graph = build_graph(fnx, n)
    checksum = 0
    if case == "list":
        for _ in range(loops):
            checksum += len(list(graph.nodes))
    elif case == "consume":
        for _ in range(loops):
            for _node in graph.nodes:
                checksum += 1
    else:
        raise ValueError(f"unknown case: {case}")
    print(checksum)


def emit_profile(n: int, loops: int) -> None:
    profiler = cProfile.Profile()
    profiler.enable()
    run_loop("list", n, loops)
    profiler.disable()
    stream = io.StringIO()
    pstats.Stats(profiler, stream=stream).strip_dirs().sort_stats("tottime").print_stats(20)
    print(stream.getvalue())


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("proof", "bench", "loop", "profile"))
    parser.add_argument("--case", choices=("list", "consume"), default="list")
    parser.add_argument("--n", type=int, default=20_000)
    parser.add_argument("--repeat", type=int, default=21)
    parser.add_argument("--loops", type=int, default=30)
    args = parser.parse_args()
    if args.mode == "proof":
        emit_proof()
    elif args.mode == "bench":
        emit_bench(args.n, args.repeat)
    elif args.mode == "loop":
        run_loop(args.case, args.n, args.loops)
    elif args.mode == "profile":
        emit_profile(args.n, args.loops)


if __name__ == "__main__":
    main()
