#!/usr/bin/env python3
"""Benchmark and proof harness for br-r37-c1-9brc9."""

from __future__ import annotations

import argparse
import cProfile
import hashlib
import json
import pstats
import statistics
import time
from pathlib import Path

import franken_networkx as fnx
import networkx as nx


CASES = (
    ("rr_4_10_seed42", 4, 10, 42),
    ("rr_4_24_seed5", 4, 24, 5),
    ("rr_8_20_seed53", 8, 20, 53),
    ("rr_10_80_seed17", 10, 80, 17),
    ("rr_20_400_seed123", 20, 400, 123),
)


def graph_payload(graph):
    return {
        "nodes": list(graph.nodes()),
        "edges": list(graph.edges()),
        "adjacency": {node: list(graph[node]) for node in graph.nodes()},
        "degrees": {node: graph.degree(node) for node in graph.nodes()},
        "edge_count": graph.number_of_edges(),
    }


def exception_payload(exc: BaseException):
    return {
        "type": type(exc).__name__,
        "message": str(exc),
    }


def canonical_json(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def sha256_obj(obj) -> str:
    return hashlib.sha256(canonical_json(obj).encode("utf-8")).hexdigest()


def direct_set_payload():
    edges = fnx._fnx.random_regular_edges_pyset(8, 20, 53)
    via_set = fnx.Graph()
    via_set.add_edges_from(edges)
    via_list = fnx.Graph()
    via_list.add_edges_from(list(edges))
    set_payload = graph_payload(via_set)
    list_payload = graph_payload(via_list)
    return {
        "name": "direct_pyset_vs_list",
        "set": set_payload,
        "list": list_payload,
        "matches": set_payload == list_payload,
        "set_iteration_sha256": sha256_obj(list(edges)),
    }


def fallback_conflict_payload():
    edge_set = {(0, 1), (1.0, 2), (2, 3), (3, 4), (4, 0), (5, 6), (6, 7), (7, 5)}
    graph = fnx.Graph()
    graph.add_edges_from(edge_set)
    return {
        "name": "hash_equal_display_conflict",
        "payload": graph_payload(graph),
        "has_int_and_float_display": 1 in graph and 1.0 in graph,
    }


def partial_error_payload():
    edge_set = {(0, 1), (1, 2), (2, 3), (3, 4), (4, 5), (5, 6), (6, 7), (8, 9, 10, 11)}
    graph = fnx.Graph()
    try:
        graph.add_edges_from(edge_set)
    except BaseException as exc:
        error = exception_payload(exc)
    else:
        error = None
    return {
        "name": "bad_arity_set_fallback",
        "error": error,
        "graph_after_error": graph_payload(graph),
    }


def global_attr_payload():
    edge_set = fnx._fnx.random_regular_edges_pyset(4, 24, 5)
    graph = fnx.Graph()
    graph.add_edges_from(edge_set, weight=7)
    payload = graph_payload(graph)
    weights = [data.get("weight") for _, _, data in graph.edges(data=True)]
    return {
        "name": "global_attr_guard",
        "payload": payload,
        "weights": weights,
        "all_weights_match": all(weight == 7 for weight in weights),
    }


def proof_payload():
    cases = []
    for name, degree, nodes, seed in CASES:
        fnx_graph = fnx.random_regular_graph(degree, nodes, seed=seed)
        nx_graph = nx.random_regular_graph(degree, nodes, seed=seed)
        fnx_payload = graph_payload(fnx_graph)
        nx_payload = graph_payload(nx_graph)
        cases.append(
            {
                "name": name,
                "degree": degree,
                "nodes": nodes,
                "seed": seed,
                "fnx": fnx_payload,
                "nx": nx_payload,
                "matches_nx": fnx_payload == nx_payload,
                "fnx_sha256": sha256_obj(fnx_payload),
                "nx_sha256": sha256_obj(nx_payload),
            }
        )
    payload = {
        "bead": "br-r37-c1-9brc9",
        "cases": cases,
        "direct_set": direct_set_payload(),
        "fallback_conflict": fallback_conflict_payload(),
        "partial_error": partial_error_payload(),
        "global_attr": global_attr_payload(),
        "all_match": all(case["matches_nx"] for case in cases),
        "ordering": "node order, edge order, and adjacency row order captured exactly",
        "tie_breaking": "CPython set iteration order is captured by edge and adjacency rows",
        "floating_point": "N/A",
        "rng": "fixed Python random.Random seeds",
    }
    payload["all_match"] = (
        payload["all_match"]
        and payload["direct_set"]["matches"]
        and payload["global_attr"]["all_weights_match"]
        and payload["partial_error"]["error"] is not None
    )
    payload["sha256"] = sha256_obj(payload)
    return payload


def timed_call(fn, repeats: int):
    samples = []
    for _ in range(repeats):
        start = time.perf_counter()
        fn()
        samples.append(time.perf_counter() - start)
    return {
        "best": min(samples),
        "median": statistics.median(samples),
        "mean": statistics.fmean(samples),
        "samples": samples,
    }


def timing_payload(repeats: int):
    payload = {"repeats": repeats, "cases": []}
    for name, degree, nodes, seed in CASES:
        fnx_timing = timed_call(
            lambda: fnx.random_regular_graph(degree, nodes, seed=seed),
            repeats,
        )
        nx_timing = timed_call(
            lambda: nx.random_regular_graph(degree, nodes, seed=seed),
            repeats,
        )
        payload["cases"].append(
            {
                "name": name,
                "degree": degree,
                "nodes": nodes,
                "seed": seed,
                "fnx": fnx_timing,
                "nx": nx_timing,
                "ratio_fnx_over_nx_median": fnx_timing["median"] / nx_timing["median"],
            }
        )
    return payload


def profile_case(output: Path, repeats: int):
    degree, nodes, seed = 20, 400, 123
    profiler = cProfile.Profile()
    profiler.enable()
    for _ in range(repeats):
        fnx.random_regular_graph(degree, nodes, seed=seed)
    profiler.disable()
    with output.open("w", encoding="utf-8") as handle:
        stats = pstats.Stats(profiler, stream=handle).sort_stats("cumulative")
        stats.print_stats(40)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("proof", "timing", "profile"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repeats", type=int, default=25)
    args = parser.parse_args()

    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.mode == "proof":
        payload = proof_payload()
        args.output.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        if not payload["all_match"]:
            raise SystemExit("proof mismatch")
    elif args.mode == "timing":
        payload = timing_payload(args.repeats)
        args.output.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    else:
        profile_case(args.output, args.repeats)


if __name__ == "__main__":
    main()
