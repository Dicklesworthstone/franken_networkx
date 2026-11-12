#!/usr/bin/env python3
"""Proof harness for br-r37-c1-04z53.76 MultiDiGraph global attrs."""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import time

import franken_networkx as fnx
import networkx as nx


def stable(value):
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    return repr(value)


def graph_signature(graph):
    nodes = [stable(node) for node in graph.nodes()]
    edges = []
    for u, v, key, data in graph.edges(keys=True, data=True):
        attrs = [[stable(k), stable(v)] for k, v in sorted(data.items(), key=lambda item: repr(item[0]))]
        edges.append([stable(u), stable(v), stable(key), attrs])
    rows = []
    for u in graph.nodes():
        for v in graph.successors(u):
            rows.append(
                [
                    stable(u),
                    stable(v),
                    [stable(key) for key in graph[u][v].keys()],
                ]
            )
    return {"nodes": nodes, "edges": edges, "rows": rows}


def sha256_payload(payload):
    data = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(data).hexdigest()


def build_case(cls, edges, attrs):
    graph = cls()
    graph.add_edges_from(edges, **attrs)
    return graph_signature(graph)


def error_case(cls):
    graph = cls()
    error = None
    try:
        graph.add_edges_from([(0, 1, "k0", {"weight": 2}), (1, 2, "bad", 3.14)], weight=1)
    except Exception as exc:  # noqa: BLE001 - exact exception class is part of the captured proof.
        error = type(exc).__name__
    return {"error": error, "state": graph_signature(graph)}


def golden_payload():
    cases = {
        "global_two_tuple_repeats": (
            [(0, 1), (0, 1), (1, 0), (2, 2), (1, 2)],
            {"weight": 1, "color": "global"},
        ),
        "global_plus_edge_overrides": (
            [
                (0, 1, {"weight": 2}),
                (0, 1, {"color": "edge"}),
                (1, 0),
                (2, 0, {"extra": 5, "weight": 9}),
            ],
            {"weight": 1, "color": "global"},
        ),
        "global_key_third_fallback": (
            [(0, 1, "k0"), (0, 1, "k1"), (1, 0, "back")],
            {"weight": 1},
        ),
    }
    result = {"cases": {}, "error_case": {}}
    for name, (edges, attrs) in cases.items():
        fnx_sig = build_case(fnx.MultiDiGraph, edges, attrs)
        nx_sig = build_case(nx.MultiDiGraph, edges, attrs)
        result["cases"][name] = {
            "fnx": fnx_sig,
            "nx": nx_sig,
            "matches_networkx": fnx_sig == nx_sig,
        }
    fnx_error = error_case(fnx.MultiDiGraph)
    nx_error = error_case(nx.MultiDiGraph)
    result["error_case"] = {
        "fnx": fnx_error,
        "nx": nx_error,
        "matches_networkx": fnx_error == nx_error,
    }
    result["all_match_networkx"] = all(case["matches_networkx"] for case in result["cases"].values()) and result[
        "error_case"
    ]["matches_networkx"]
    result["sha256"] = sha256_payload(result)
    return result


def make_edges(n, m):
    return [(i % n, (i * 7 + 1) % n) for i in range(m)]


def construct(cls, edges):
    graph = cls()
    graph.add_edges_from(edges, weight=1)
    return graph


def bench_payload(n, m, loops, repeats):
    edges = make_edges(n, m)
    result = {"n": n, "m": m, "loops": loops, "repeats": repeats, "results": {}}
    for name, cls in (("fnx", fnx.MultiDiGraph), ("networkx", nx.MultiDiGraph)):
        samples = []
        digest = None
        for _ in range(repeats):
            start = time.perf_counter()
            graph = None
            for _ in range(loops):
                graph = construct(cls, edges)
            elapsed = (time.perf_counter() - start) / loops
            samples.append(elapsed)
            if digest is None:
                digest = sha256_payload(graph_signature(graph))
        result["results"][name] = {
            "median_seconds": statistics.median(samples),
            "best_seconds": min(samples),
            "samples_seconds": samples,
            "digest": digest,
        }
    result["results"]["fnx"]["vs_networkx_median_ratio"] = (
        result["results"]["networkx"]["median_seconds"] / result["results"]["fnx"]["median_seconds"]
    )
    result["sha256"] = sha256_payload(result)
    return result


def one_payload(n, m, loops):
    edges = make_edges(n, m)
    graph = None
    for _ in range(loops):
        graph = construct(fnx.MultiDiGraph, edges)
    payload = {"loops": loops, "n": n, "m": m, "digest": sha256_payload(graph_signature(graph))}
    print(json.dumps(payload, sort_keys=True))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("golden", "bench", "one"))
    parser.add_argument("--n", type=int, default=2000)
    parser.add_argument("--m", type=int, default=8000)
    parser.add_argument("--loops", type=int, default=60)
    parser.add_argument("--repeats", type=int, default=9)
    args = parser.parse_args()

    if args.mode == "golden":
        print(json.dumps(golden_payload(), indent=2, sort_keys=True))
    elif args.mode == "bench":
        print(json.dumps(bench_payload(args.n, args.m, args.loops, args.repeats), indent=2, sort_keys=True))
    else:
        one_payload(args.n, args.m, args.loops)


if __name__ == "__main__":
    main()
