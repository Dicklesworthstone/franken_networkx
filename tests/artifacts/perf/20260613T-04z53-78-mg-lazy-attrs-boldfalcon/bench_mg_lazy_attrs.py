#!/usr/bin/env python3
"""Proof harness for br-r37-c1-04z53.78 MultiGraph lazy attr mirrors."""

from __future__ import annotations

import argparse
import cProfile
import hashlib
import hmac
import io
import json
import pstats
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
        for v in graph.neighbors(u):
            rows.append([stable(u), stable(v), [stable(key) for key in graph[u][v].keys()]])
    return {"nodes": nodes, "edges": edges, "rows": rows}


def sha256_payload(payload):
    data = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(data).hexdigest()


def same_payload(left, right):
    return hmac.compare_digest(sha256_payload(left), sha256_payload(right))


def identity_mutation_case(cls):
    graph = cls()
    graph.add_edges_from([(0, 1), (1, 0), (0, 1), (2, 2)], weight=1, color="global")

    all_data = graph.get_edge_data(0, 1)
    edge0 = graph.get_edge_data(0, 1, 0)
    edge0_again = graph[0][1][0]
    all_data[0]["weight"] = 7
    edge0_again["new"] = "seen"
    graph.get_edge_data(1, 0, 1)["color"] = "reverse"

    return {
        "same_identity": edge0 is edge0_again,
        "all_data_identity": all_data[0] is edge0,
        "edge0": [[stable(k), stable(v)] for k, v in sorted(edge0.items(), key=lambda item: repr(item[0]))],
        "signature": graph_signature(graph),
    }


def explicit_key_fallback_case(cls):
    graph = cls()
    error = None
    try:
        graph.add_edges_from([(0, 1, "k0"), (0, 1, "k1")], weight=1)
    except Exception as exc:  # noqa: BLE001 - captured for parity proof.
        error = type(exc).__name__
    return {"error": error, "signature": graph_signature(graph)}


def derived_graph_case(cls):
    graph = cls()
    graph.add_edges_from([(0, 1), (0, 1), (1, 0), (2, 2)], weight=3, color="global")
    copy_graph = graph.copy()
    directed_graph = graph.to_directed()
    return {
        "copy": graph_signature(copy_graph),
        "to_directed": graph_signature(directed_graph),
    }


def build_case(cls, edges, attrs):
    graph = cls()
    graph.add_edges_from(edges, **attrs)
    return graph_signature(graph)


def golden_payload():
    cases = {
        "global_only_repeated_pairs": (
            [(0, 1), (1, 0), (0, 1), (2, 2), (1, 2)],
            {"weight": 1, "color": "global"},
        ),
        "global_plus_edge_overrides": (
            [
                (0, 1, {"weight": 2}),
                (1, 0, {"color": "edge"}),
                (2, 0),
                (2, 0, {"extra": 5, "weight": 9}),
            ],
            {"weight": 1, "color": "global"},
        ),
    }
    result = {"cases": {}, "identity_mutation": {}, "explicit_key_fallback": {}, "derived_graphs": {}}
    for name, (edges, attrs) in cases.items():
        fnx_sig = build_case(fnx.MultiGraph, edges, attrs)
        nx_sig = build_case(nx.MultiGraph, edges, attrs)
        result["cases"][name] = {
            "fnx": fnx_sig,
            "nx": nx_sig,
            "matches_networkx": same_payload(fnx_sig, nx_sig),
        }

    fnx_identity = identity_mutation_case(fnx.MultiGraph)
    nx_identity = identity_mutation_case(nx.MultiGraph)
    result["identity_mutation"] = {
        "fnx": fnx_identity,
        "nx": nx_identity,
        "matches_networkx": same_payload(fnx_identity, nx_identity),
    }

    fnx_fallback = explicit_key_fallback_case(fnx.MultiGraph)
    nx_fallback = explicit_key_fallback_case(nx.MultiGraph)
    result["explicit_key_fallback"] = {
        "fnx": fnx_fallback,
        "nx": nx_fallback,
        "matches_networkx": same_payload(fnx_fallback, nx_fallback),
    }

    fnx_derived = derived_graph_case(fnx.MultiGraph)
    nx_derived = derived_graph_case(nx.MultiGraph)
    result["derived_graphs"] = {
        "fnx": fnx_derived,
        "nx": nx_derived,
        "matches_networkx": same_payload(fnx_derived, nx_derived),
    }

    result["all_match_networkx"] = (
        all(case["matches_networkx"] for case in result["cases"].values())
        and result["identity_mutation"]["matches_networkx"]
        and result["explicit_key_fallback"]["matches_networkx"]
        and result["derived_graphs"]["matches_networkx"]
    )
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
    for name, cls in (("fnx", fnx.MultiGraph), ("networkx", nx.MultiGraph)):
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
        graph = construct(fnx.MultiGraph, edges)
    payload = {"loops": loops, "n": n, "m": m, "digest": sha256_payload(graph_signature(graph))}
    print(json.dumps(payload, sort_keys=True))


def profile_payload(n, m, loops):
    edges = make_edges(n, m)
    profile = cProfile.Profile()
    profile.enable()
    graph = None
    for _ in range(loops):
        graph = construct(fnx.MultiGraph, edges)
    profile.disable()
    print(json.dumps({"loops": loops, "n": n, "m": m, "digest": sha256_payload(graph_signature(graph))}))
    stream = io.StringIO()
    pstats.Stats(profile, stream=stream).sort_stats("cumulative").print_stats(35)
    print(stream.getvalue())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("golden", "bench", "one", "profile"))
    parser.add_argument("--n", type=int, default=2000)
    parser.add_argument("--m", type=int, default=8000)
    parser.add_argument("--loops", type=int, default=60)
    parser.add_argument("--repeats", type=int, default=9)
    args = parser.parse_args()

    if args.mode == "golden":
        print(json.dumps(golden_payload(), indent=2, sort_keys=True))
    elif args.mode == "bench":
        print(json.dumps(bench_payload(args.n, args.m, args.loops, args.repeats), indent=2, sort_keys=True))
    elif args.mode == "profile":
        profile_payload(args.n, args.m, args.loops)
    else:
        one_payload(args.n, args.m, args.loops)


if __name__ == "__main__":
    main()
