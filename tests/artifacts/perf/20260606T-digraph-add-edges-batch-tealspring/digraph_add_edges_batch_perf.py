#!/usr/bin/env python3
"""br-r37-c1-35cg6 proof and benchmark for directed edge batch ingest."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import statistics
import sys
import time
from collections.abc import Callable

import franken_networkx as fnx
import networkx as nx


def edge_list(seed: int = 17, n: int = 1500, m: int = 5200) -> list[tuple[int, int]]:
    rng = random.Random(seed)
    edges: list[tuple[int, int]] = [(i, (i + 1) % n) for i in range(n)]
    while len(edges) < m:
        u = rng.randrange(n)
        v = rng.randrange(n)
        if u != v:
            edges.append((u, v))
    return edges


def attr_edge_list() -> list[tuple[int, int, dict[str, object]]]:
    return [(u, v, {"w": (u * 31 + v) % 97, "tag": f"{u}:{v}"}) for u, v in edge_list()]


def graph_digest(graph) -> dict[str, object]:
    nodes = list(graph.nodes(data=True))
    edges = list(graph.edges(data=True))
    node_order = [repr(node) for node, _ in nodes]
    return {
        "nodes": [[repr(node), dict(attrs)] for node, attrs in nodes],
        "edges": [[repr(u), repr(v), dict(attrs)] for u, v, attrs in edges],
        "succ": {
            repr(node): [repr(neighbor) for neighbor in graph.succ[node]]
            for node in graph.nodes()
        },
        "pred": {
            repr(node): [repr(neighbor) for neighbor in graph.pred[node]]
            for node in graph.nodes()
        },
        "node_order": node_order,
    }


def apply_case(lib, case: dict[str, object]) -> dict[str, object]:
    graph = lib.DiGraph()
    try:
        if case["mode"] == "method":
            graph.add_edges_from(case["edges"], **case.get("attr", {}))
        elif case["mode"] == "ctor":
            graph = lib.DiGraph(case["edges"], **case.get("graph_attr", {}))
        else:
            raise AssertionError(case["mode"])
    except Exception as exc:  # noqa: BLE001 - error shape is part of the proof.
        return {
            "error_type": type(exc).__name__,
            "error": str(exc),
            "graph": graph_digest(graph),
        }
    return {"graph": graph_digest(graph)}


def proof_cases() -> list[dict[str, object]]:
    return [
        {
            "name": "plain",
            "mode": "method",
            "edges": [(0, 1), (1, 2), (2, 0), (2, 0), (3, 3)],
        },
        {
            "name": "attr",
            "mode": "method",
            "edges": [
                (0, 1, {"w": 1, "label": "a"}),
                (1, 2, {"w": 2}),
                (0, 1, {"extra": True}),
                (3, 3, {"self": "loop"}),
            ],
        },
        {
            "name": "global_attr",
            "mode": "method",
            "edges": [(0, 1), (1, 2, {"local": 7})],
            "attr": {"color": "red"},
        },
        {
            "name": "mixed_hash_equal",
            "mode": "method",
            "edges": [(7, 28.0), (28.0, 5), (7.0, 9)],
        },
        {
            "name": "bad_third_partial",
            "mode": "method",
            "edges": [(0, 1), (2, 3, 1.5), (4, 5)],
        },
        {
            "name": "ctor_plain",
            "mode": "ctor",
            "edges": [(0, 1), (1, 2), (2, 0), (4, 4)],
        },
        {
            "name": "ctor_attr",
            "mode": "ctor",
            "edges": [(0, 1, {"w": 1}), (1, 2, {"w": 2}), (0, 1, {"z": 3})],
        },
    ]


def run_proof() -> None:
    cases = []
    parity_cases = 0
    known_nonparity_cases = 0
    for case in proof_cases():
        fnx_result = apply_case(fnx, case)
        nx_result = apply_case(nx, case)
        known_nonparity = case["name"] == "bad_third_partial"
        if fnx_result != nx_result and not known_nonparity:
            raise AssertionError(
                json.dumps(
                    {"case": case["name"], "fnx": fnx_result, "nx": nx_result},
                    sort_keys=True,
                )
            )
        if known_nonparity:
            known_nonparity_cases += 1
        else:
            parity_cases += 1
        cases.append(
            {
                "case": case["name"],
                "fnx": fnx_result,
                "matches_nx": fnx_result == nx_result,
                "nx": nx_result,
            }
        )
    payload = {"cases": cases}
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    print(
        json.dumps(
            {
                "cases": len(cases),
                "golden_sha256": hashlib.sha256(blob).hexdigest(),
                "known_nonparity_cases": known_nonparity_cases,
                "parity_cases": parity_cases,
            },
            sort_keys=True,
        )
    )


def best_time(func: Callable[[], object], loops: int, samples: int) -> dict[str, float]:
    times: list[float] = []
    for _ in range(samples):
        start = time.perf_counter()
        for _ in range(loops):
            func()
        times.append((time.perf_counter() - start) / loops)
    return {
        "best_s": min(times),
        "mean_s": statistics.mean(times),
        "median_s": statistics.median(times),
    }


def build_method(lib, edges) -> int:
    graph = lib.DiGraph()
    graph.add_edges_from(edges)
    return graph.number_of_edges()


def build_ctor(lib, edges) -> int:
    graph = lib.DiGraph(edges)
    return graph.number_of_edges()


def run_bench() -> None:
    plain = edge_list()
    attributed = attr_edge_list()
    scenarios = []
    for name, edges, loops in (
        ("method_plain", plain, 18),
        ("ctor_plain", plain, 18),
        ("method_attr", attributed, 10),
        ("ctor_attr", attributed, 10),
    ):
        if name.startswith("method"):
            fnx_stats = best_time(lambda edges=edges: build_method(fnx, edges), loops, 7)
            nx_stats = best_time(lambda edges=edges: build_method(nx, edges), loops, 7)
        else:
            fnx_stats = best_time(lambda edges=edges: build_ctor(fnx, edges), loops, 7)
            nx_stats = best_time(lambda edges=edges: build_ctor(nx, edges), loops, 7)
        scenarios.append(
            {
                "name": name,
                "edges": len(edges),
                "fnx": fnx_stats,
                "nx": nx_stats,
                "fnx_vs_nx_best_ratio": fnx_stats["best_s"] / nx_stats["best_s"],
            }
        )
    print(json.dumps({"scenarios": scenarios}, indent=2, sort_keys=True))


def run_profile() -> None:
    plain = edge_list()
    attributed = attr_edge_list()
    for _ in range(80):
        build_method(fnx, plain)
        build_method(fnx, attributed)
        build_ctor(fnx, plain)
        build_ctor(fnx, attributed)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("proof", "bench", "profile"))
    args = parser.parse_args()
    if args.command == "proof":
        run_proof()
    elif args.command == "bench":
        run_bench()
    elif args.command == "profile":
        run_profile()
    else:
        raise AssertionError(args.command)
    return 0


if __name__ == "__main__":
    sys.exit(main())
