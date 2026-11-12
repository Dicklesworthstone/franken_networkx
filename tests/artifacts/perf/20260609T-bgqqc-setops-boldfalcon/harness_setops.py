#!/usr/bin/env python3
import argparse
import cProfile
import hashlib
import json
import pstats
import statistics
import time

import franken_networkx as fnx
import networkx as nx


def _edge_pairs(n: int, offset: int, step: int) -> list[tuple[int, int]]:
    return [(i, (i + offset) % n) for i in range(0, n, step)]


def build_graph(lib, kind: str, n: int):
    cls = lib.DiGraph if kind == "digraph" else lib.Graph
    g = cls()
    h = cls()
    g.add_nodes_from(range(n))
    h.add_nodes_from(range(n))
    common = _edge_pairs(n, 1, 1)
    g_only = _edge_pairs(n, 7, 2)
    h_only = _edge_pairs(n, 11, 3)
    g.add_edges_from(common)
    h.add_edges_from(common)
    g.add_edges_from(g_only)
    h.add_edges_from(h_only)
    return g, h


def run_op(lib, op: str, kind: str, n: int):
    g, h = build_graph(lib, kind, n)
    if op == "difference":
        return lib.difference(g, h)
    if op == "symmetric_difference":
        return lib.symmetric_difference(g, h)
    raise ValueError(op)


def canonical_result(result):
    return {
        "class": type(result).__name__,
        "directed": result.is_directed(),
        "multigraph": result.is_multigraph(),
        "graph": sorted(result.graph.items(), key=lambda item: repr(item[0])),
        "nodes": list(result.nodes(data=True)),
        "edges": list(result.edges(data=True)),
        "adj": [
            (node, list(result.adj[node].keys()))
            for node in result.nodes()
        ],
    }


def proof(n: int):
    payload = []
    for kind in ("graph", "digraph"):
        for op in ("difference", "symmetric_difference"):
            fnx_result = canonical_result(run_op(fnx, op, kind, n))
            nx_result = canonical_result(run_op(nx, op, kind, n))
            payload.append(
                {
                    "kind": kind,
                    "op": op,
                    "matches_nx": fnx_result == nx_result,
                    "fnx": fnx_result,
                    "nx": nx_result,
                }
            )
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return {
        "sha256": hashlib.sha256(encoded).hexdigest(),
        "all_match": all(item["matches_nx"] for item in payload),
        "cases": payload,
    }


def timing(lib_name: str, op: str, kind: str, n: int, repeat: int):
    lib = fnx if lib_name == "fnx" else nx
    samples = []
    for _ in range(repeat):
        g, h = build_graph(lib, kind, n)
        start = time.perf_counter()
        if op == "difference":
            result = lib.difference(g, h)
        else:
            result = lib.symmetric_difference(g, h)
        samples.append(time.perf_counter() - start)
        if result.number_of_nodes() != n:
            raise AssertionError("unexpected node count")
    return {
        "lib": lib_name,
        "op": op,
        "kind": kind,
        "n": n,
        "repeat": repeat,
        "samples": samples,
        "mean": statistics.fmean(samples),
        "median": statistics.median(samples),
        "min": min(samples),
        "max": max(samples),
    }


def profile(lib_name: str, op: str, kind: str, n: int, repeat: int, output: str):
    profiler = cProfile.Profile()
    profiler.enable()
    timing(lib_name, op, kind, n, repeat)
    profiler.disable()
    with open(output, "w", encoding="utf-8") as handle:
        stats = pstats.Stats(profiler, stream=handle)
        stats.strip_dirs().sort_stats("cumulative").print_stats(40)


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)

    timing_parser = sub.add_parser("timing")
    timing_parser.add_argument("--lib", choices=("fnx", "nx"), required=True)
    timing_parser.add_argument("--op", choices=("difference", "symmetric_difference"), required=True)
    timing_parser.add_argument("--kind", choices=("graph", "digraph"), required=True)
    timing_parser.add_argument("--n", type=int, default=1600)
    timing_parser.add_argument("--repeat", type=int, default=30)

    proof_parser = sub.add_parser("proof")
    proof_parser.add_argument("--n", type=int, default=96)

    profile_parser = sub.add_parser("profile")
    profile_parser.add_argument("--lib", choices=("fnx", "nx"), required=True)
    profile_parser.add_argument("--op", choices=("difference", "symmetric_difference"), required=True)
    profile_parser.add_argument("--kind", choices=("graph", "digraph"), required=True)
    profile_parser.add_argument("--n", type=int, default=1600)
    profile_parser.add_argument("--repeat", type=int, default=30)
    profile_parser.add_argument("--output", required=True)

    args = parser.parse_args()
    if args.cmd == "timing":
        print(json.dumps(timing(args.lib, args.op, args.kind, args.n, args.repeat), sort_keys=True))
    elif args.cmd == "proof":
        print(json.dumps(proof(args.n), sort_keys=True))
    else:
        profile(args.lib, args.op, args.kind, args.n, args.repeat, args.output)


if __name__ == "__main__":
    main()
