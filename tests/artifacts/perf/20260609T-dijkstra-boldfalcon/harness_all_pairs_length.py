#!/usr/bin/env python3
"""Benchmark/proof harness for br-r37-c1-04z53 all-pairs Dijkstra length work."""

from __future__ import annotations

import argparse
import cProfile
import hashlib
import json
import pstats
import statistics
import time
from io import StringIO

import networkx as nx

import franken_networkx as fnx
import franken_networkx._fnx as _fnx


def build_pair(n: int, *, directed: bool = False):
    graph_cls = fnx.DiGraph if directed else fnx.Graph
    nx_cls = nx.DiGraph if directed else nx.Graph
    g = graph_cls()
    h = nx_cls()
    for node in range(n):
        g.add_node(node)
        h.add_node(node)
    for node in range(n - 1):
        g.add_edge(node, node + 1)
        h.add_edge(node, node + 1)
    for node in range(n):
        target = (node * 7 + 13) % n
        if target != node:
            g.add_edge(node, target)
            h.add_edge(node, target)
    return g, h


def normalize_public(result):
    return [
        [source, [[target, dist] for target, dist in lengths.items()]]
        for source, lengths in result.items()
    ]


def public_result(lib: str, n: int, *, directed: bool = False):
    g, h = build_pair(n, directed=directed)
    if lib == "fnx":
        return dict(fnx.all_pairs_dijkstra_path_length(g))
    if lib == "nx":
        return dict(nx.all_pairs_dijkstra_path_length(h))
    raise ValueError(lib)


def raw_result(n: int, *, directed: bool = False):
    g, _ = build_pair(n, directed=directed)
    return _fnx.all_pairs_dijkstra_path_length(g, "weight")


def time_call(fn, samples: int):
    timings = []
    checksum = None
    for _ in range(samples):
        start = time.perf_counter()
        result = fn()
        timings.append(time.perf_counter() - start)
        checksum = hashlib.sha256(
            json.dumps(normalize_public(result), separators=(",", ":")).encode()
        ).hexdigest()
    return {
        "samples": samples,
        "min_s": min(timings),
        "median_s": statistics.median(timings),
        "mean_s": statistics.mean(timings),
        "checksum": checksum,
    }


def run_proof(n: int):
    cases = []
    for directed in (False, True):
        fnx_payload = normalize_public(public_result("fnx", n, directed=directed))
        nx_payload = normalize_public(public_result("nx", n, directed=directed))
        cases.append(
            {
                "case": "digraph" if directed else "graph",
                "matches_networkx": fnx_payload == nx_payload,
                "fnx_sha256": hashlib.sha256(
                    json.dumps(fnx_payload, separators=(",", ":")).encode()
                ).hexdigest(),
                "nx_sha256": hashlib.sha256(
                    json.dumps(nx_payload, separators=(",", ":")).encode()
                ).hexdigest(),
            }
        )
    payload = {
        "n": n,
        "cases": cases,
        "ordering": "outer node insertion order; inner Dijkstra finalize order",
        "tie_breaking": "NetworkX heap-pop order preserved by public output",
        "floating_point": "missing weights are integer default 1; public output keeps int distances",
        "rng": "N/A; graph fixture is deterministic arithmetic",
    }
    print(json.dumps(payload, indent=2, sort_keys=True))


def run_timing(args):
    directed = args.graph == "digraph"
    if args.impl == "fnx":
        fn = lambda: public_result("fnx", args.nodes, directed=directed)
    elif args.impl == "nx":
        fn = lambda: public_result("nx", args.nodes, directed=directed)
    elif args.impl == "raw":
        fn = lambda: raw_result(args.nodes, directed=directed)
    else:
        raise ValueError(args.impl)
    result = time_call(fn, args.samples)
    result.update({"impl": args.impl, "graph": args.graph, "nodes": args.nodes})
    print(json.dumps(result, sort_keys=True))


def run_command(args):
    directed = args.graph == "digraph"
    if args.impl == "fnx":
        fn = lambda: public_result("fnx", args.nodes, directed=directed)
    elif args.impl == "nx":
        fn = lambda: public_result("nx", args.nodes, directed=directed)
    elif args.impl == "raw":
        fn = lambda: raw_result(args.nodes, directed=directed)
    else:
        raise ValueError(args.impl)
    checksum = None
    start = time.perf_counter()
    for _ in range(args.iters):
        result = fn()
        checksum = hashlib.sha256(
            json.dumps(normalize_public(result), separators=(",", ":")).encode()
        ).hexdigest()
    elapsed = time.perf_counter() - start
    print(
        json.dumps(
            {
                "impl": args.impl,
                "graph": args.graph,
                "nodes": args.nodes,
                "iters": args.iters,
                "elapsed_s": elapsed,
                "checksum": checksum,
            },
            sort_keys=True,
        )
    )


def run_profile(args):
    directed = args.graph == "digraph"
    fn = lambda: public_result("fnx", args.nodes, directed=directed)
    profiler = cProfile.Profile()
    profiler.enable()
    for _ in range(args.iters):
        fn()
    profiler.disable()
    stream = StringIO()
    pstats.Stats(profiler, stream=stream).strip_dirs().sort_stats("cumtime").print_stats(30)
    print(stream.getvalue())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("proof", "timing", "command", "profile"), required=True)
    parser.add_argument("--impl", choices=("fnx", "nx", "raw"), default="fnx")
    parser.add_argument("--graph", choices=("graph", "digraph"), default="graph")
    parser.add_argument("--nodes", type=int, default=96)
    parser.add_argument("--samples", type=int, default=15)
    parser.add_argument("--iters", type=int, default=3)
    args = parser.parse_args()
    if args.mode == "proof":
        run_proof(args.nodes)
    elif args.mode == "timing":
        run_timing(args)
    elif args.mode == "command":
        run_command(args)
    else:
        run_profile(args)


if __name__ == "__main__":
    main()
