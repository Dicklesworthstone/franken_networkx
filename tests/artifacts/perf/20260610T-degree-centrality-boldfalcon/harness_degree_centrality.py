#!/usr/bin/env python3
"""Evidence harness for degree_centrality_5k regression."""

from __future__ import annotations

import argparse
import cProfile
import hashlib
import io
import json
import pstats
import statistics
import time

import franken_networkx as fnx
import networkx as nx


NX_DEGREE_CENTRALITY = getattr(nx.degree_centrality, "orig_func", nx.degree_centrality)


def copy_to_fnx(graph):
    out = fnx.Graph()
    out.add_nodes_from(graph.nodes(data=True))
    out.add_edges_from(graph.edges(data=True))
    return out


def build_graph(n: int, m: int):
    nx_graph = nx.barabasi_albert_graph(n, m, seed=42)
    return nx_graph, copy_to_fnx(nx_graph)


def degree_call(graph, impl: str):
    if impl == "fnx":
        return fnx.degree_centrality(graph)
    return NX_DEGREE_CENTRALITY(graph)


def canonical(result: dict[object, float]) -> str:
    rows = [(repr(node), format(float(score), ".17g")) for node, score in result.items()]
    return json.dumps(rows, separators=(",", ":"))


def timed(call, loops: int):
    values = []
    result = call()
    for _ in range(loops):
        start = time.perf_counter()
        result = call()
        values.append(time.perf_counter() - start)
    return values, result


def bench(args: argparse.Namespace) -> None:
    nx_graph, fnx_graph = build_graph(args.n, args.m)
    graph = fnx_graph if args.impl == "fnx" else nx_graph
    values, result = timed(lambda: degree_call(graph, args.impl), args.loops)
    payload = canonical(result)
    print(
        json.dumps(
            {
                "impl": args.impl,
                "n": args.n,
                "m": args.m,
                "edges": nx_graph.number_of_edges(),
                "loops": args.loops,
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
    cases = []
    cases.append(("empty", nx.Graph()))
    single = nx.Graph()
    single.add_node("a")
    cases.append(("single", single))
    path = nx.path_graph(5)
    cases.append(("path5", path))
    loop = nx.Graph()
    loop.add_edge("x", "x")
    loop.add_edge("x", "y")
    cases.append(("self_loop", loop))
    cases.append((f"ba_{args.n}_{args.m}", nx.barabasi_albert_graph(args.n, args.m, seed=42)))

    rows = []
    for label, nx_graph in cases:
        fnx_graph = copy_to_fnx(nx_graph)
        nx_result = degree_call(nx_graph, "nx")
        fnx_result = degree_call(fnx_graph, "fnx")
        nx_payload = canonical(nx_result)
        fnx_payload = canonical(fnx_result)
        rows.append(
            {
                "case": label,
                "nx_sha256": hashlib.sha256(nx_payload.encode()).hexdigest(),
                "fnx_sha256": hashlib.sha256(fnx_payload.encode()).hexdigest(),
                "matches_nx": nx_payload == fnx_payload,
            }
        )

    payload = {
        "cases": rows,
        "all_match": all(row["matches_nx"] for row in rows),
        "ordering": "NetworkX and FNX both emit nodes in graph insertion order.",
        "tie_breaking": "No ties are resolved; degree centrality is per-node arithmetic.",
        "floating_point": "Both paths use score = degree * (1.0 / (n - 1)); exact string hashes checked.",
        "rng": "Only deterministic BA graph construction with seed=42.",
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    payload["proof_sha256"] = hashlib.sha256(encoded.encode()).hexdigest()
    print(json.dumps(payload, indent=2, sort_keys=True))


def profile(args: argparse.Namespace) -> None:
    _, fnx_graph = build_graph(args.n, args.m)
    degree_call(fnx_graph, "fnx")
    profiler = cProfile.Profile()
    profiler.enable()
    for _ in range(args.loops):
        degree_call(fnx_graph, "fnx")
    profiler.disable()
    stream = io.StringIO()
    pstats.Stats(profiler, stream=stream).sort_stats("cumtime").print_stats(args.limit)
    print(stream.getvalue())


def main() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name in ("bench", "proof", "profile"):
        sub = subparsers.add_parser(name)
        sub.add_argument("--n", type=int, default=5000)
        sub.add_argument("--m", type=int, default=5)
        sub.add_argument("--loops", type=int, default=200)
        if name == "bench":
            sub.add_argument("--impl", choices=("fnx", "nx"), required=True)
        if name == "profile":
            sub.add_argument("--limit", type=int, default=32)
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
