#!/usr/bin/env python3
"""Evidence harness for br-r37-c1-f2ohl weighted pagerank sync."""

from __future__ import annotations

import argparse
import cProfile
import hashlib
import io
import json
import math
import pstats
import statistics
import time
from collections.abc import Callable

import franken_networkx as fnx
import networkx as nx


OFFSETS = (1, 7, 17, 31)


def build_graphs(n: int, *, mutate_edges: bool = False):
    fnx_graph = fnx.DiGraph()
    nx_graph = nx.DiGraph()
    node_rows = [
        (
            i,
            {
                "payload": f"node-{i:05d}",
                "rank": i,
                "group": i % 17,
                "active": (i % 3) == 0,
                "label": f"group-{i % 17}",
                "score": (i % 101) / 101.0,
                "left": i - 1,
                "right": i + 1,
                "stamp": f"2026-06-10:{i % 60:02d}",
                "kind": "pagerank-sync-bench",
                "odd": (i & 1) == 1,
                "mod7": i % 7,
            },
        )
        for i in range(n)
    ]
    fnx_graph.add_nodes_from(node_rows)
    nx_graph.add_nodes_from(node_rows)
    edges = []
    for i in range(n):
        for offset in OFFSETS:
            target = (i + offset) % n
            weight = ((i * 131 + offset * 17) % 97 + 1) / 97.0
            edges.append((i, target, {"weight": weight}))
    fnx_graph.add_edges_from(edges)
    nx_graph.add_edges_from(edges)
    if mutate_edges:
        for i in range(0, n, max(1, n // 97)):
            target = (i + OFFSETS[i % len(OFFSETS)]) % n
            weight = ((i * 19 + 11) % 53 + 1) / 53.0
            fnx_graph[i][target]["weight"] = weight
            nx_graph[i][target]["weight"] = weight
    return fnx_graph, nx_graph


def pagerank_call(graph, impl: str):
    module = fnx if impl == "fnx" else nx
    return module.pagerank(graph, weight="weight", tol=1e-8, max_iter=100)


def timed(call: Callable[[], object], loops: int):
    values = []
    result = None
    call()
    for _ in range(loops):
        start = time.perf_counter()
        result = call()
        values.append(time.perf_counter() - start)
    return values, result


def canonical(result: dict[int, float]) -> str:
    rows = [(int(node), format(float(score), ".17g")) for node, score in result.items()]
    return json.dumps(rows, separators=(",", ":"))


def bench(args: argparse.Namespace) -> None:
    fnx_graph, nx_graph = build_graphs(args.n, mutate_edges=args.mutate_edges)
    graph = fnx_graph if args.impl == "fnx" else nx_graph
    values, result = timed(lambda: pagerank_call(graph, args.impl), args.loops)
    payload = canonical(result)
    print(
        json.dumps(
            {
                "impl": args.impl,
                "n": args.n,
                "edges": len(OFFSETS) * args.n,
                "loops": args.loops,
                "mutate_edges": args.mutate_edges,
                "median_s": statistics.median(values),
                "mean_s": statistics.fmean(values),
                "min_s": min(values),
                "max_s": max(values),
                "sha256": hashlib.sha256(payload.encode()).hexdigest(),
            },
            sort_keys=True,
        )
    )


def proof(args: argparse.Namespace) -> None:
    cases = [
        ("clean", build_graphs(args.n, mutate_edges=False)),
        ("dirty_edges", build_graphs(args.n, mutate_edges=True)),
    ]
    rows = []
    max_abs = 0.0
    max_rel = 0.0
    for label, (fnx_graph, nx_graph) in cases:
        fnx_result = pagerank_call(fnx_graph, "fnx")
        nx_result = pagerank_call(nx_graph, "nx")
        case_abs = max(abs(fnx_result[node] - nx_result[node]) for node in nx_result)
        case_rel = max(
            abs(fnx_result[node] - nx_result[node]) / max(abs(nx_result[node]), 1e-300)
            for node in nx_result
        )
        max_abs = max(max_abs, case_abs)
        max_rel = max(max_rel, case_rel)
        rows.append(
            {
                "case": label,
                "fnx_sha256": hashlib.sha256(canonical(fnx_result).encode()).hexdigest(),
                "nx_sha256": hashlib.sha256(canonical(nx_result).encode()).hexdigest(),
                "max_abs": case_abs,
                "max_rel": case_rel,
            }
        )
    proof_payload = {
        "n": args.n,
        "edges": len(OFFSETS) * args.n,
        "cases": rows,
        "max_abs": max_abs,
        "max_rel": max_rel,
        "all_close": max_abs <= 1e-15 or (max_abs <= 1e-12 and max_rel <= 1e-9),
        "ordering": "pagerank returns dict(zip(list(G), x)); node insertion order unchanged",
        "tie_breaking": "no ordering-dependent ties; matrix rows follow list(G)",
        "floating_point": "same scipy sparse power iteration path; only pre-sync route changes",
        "rng": "none; deterministic modular edge schedule",
    }
    encoded = json.dumps(proof_payload, sort_keys=True, separators=(",", ":"))
    proof_payload["proof_sha256"] = hashlib.sha256(encoded.encode()).hexdigest()
    print(json.dumps(proof_payload, indent=2, sort_keys=True))


def profile(args: argparse.Namespace) -> None:
    fnx_graph, _ = build_graphs(args.n, mutate_edges=args.mutate_edges)
    pagerank_call(fnx_graph, "fnx")
    profiler = cProfile.Profile()
    profiler.enable()
    for _ in range(args.loops):
        pagerank_call(fnx_graph, "fnx")
    profiler.disable()
    stream = io.StringIO()
    pstats.Stats(profiler, stream=stream).sort_stats("cumtime").print_stats(args.limit)
    print(stream.getvalue())


def main() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name in ("bench", "proof", "profile"):
        sub = subparsers.add_parser(name)
        sub.add_argument("--n", type=int, default=1200)
        sub.add_argument("--loops", type=int, default=20)
        sub.add_argument("--mutate-edges", action="store_true")
        if name == "bench":
            sub.add_argument("--impl", choices=("fnx", "nx"), required=True)
        if name == "profile":
            sub.add_argument("--limit", type=int, default=24)
    args = parser.parse_args()
    if args.command == "bench":
        bench(args)
    elif args.command == "proof":
        proof(args)
    elif args.command == "profile":
        profile(args)
    else:
        raise AssertionError(args.command)


if __name__ == "__main__":
    main()
