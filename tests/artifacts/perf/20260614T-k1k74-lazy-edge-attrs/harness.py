#!/usr/bin/env python3
import argparse
import cProfile
import hashlib
import json
import pstats
import statistics
import sys
import time
from pathlib import Path

import networkx as nx
import franken_networkx as fnx


def build_edges(n: int, *, weighted: bool) -> list[tuple[int, int, dict]]:
    edges = []
    for i in range(n):
        u = i * 2
        v = u + 1
        attrs = {"w": (i % 17) + 1, "tag": f"e{i % 23}"} if weighted else {}
        edges.append((u, v, attrs))
    return edges


def source_graph(lib, graph_kind: str, n: int, *, weighted: bool):
    if graph_kind == "graph":
        graph = lib.Graph()
        graph.add_edges_from(build_edges(n, weighted=weighted))
        return graph
    if graph_kind == "multigraph":
        graph = lib.MultiGraph()
        for i, (u, v, attrs) in enumerate(build_edges(n, weighted=weighted)):
            graph.add_edge(u, v, key=i % 3, **attrs)
        return graph
    raise ValueError(graph_kind)


def construct(lib, scenario: str, n: int, *, weighted: bool):
    if scenario == "multidigraph_from_graph":
        return lib.MultiDiGraph(source_graph(lib, "graph", n, weighted=weighted))
    if scenario == "multidigraph_from_multigraph":
        return lib.MultiDiGraph(source_graph(lib, "multigraph", n, weighted=weighted))
    if scenario == "digraph_from_multigraph":
        return lib.DiGraph(source_graph(lib, "multigraph", n, weighted=weighted))
    if scenario == "multigraph_from_graph":
        return lib.MultiGraph(source_graph(lib, "graph", n, weighted=weighted))
    raise ValueError(scenario)


def digest_graph(graph) -> str:
    payload = {
        "class": graph.__class__.__name__,
        "directed": graph.is_directed(),
        "multigraph": graph.is_multigraph(),
        "nodes": [(repr(node), sorted(attrs.items())) for node, attrs in graph.nodes(data=True)],
        "edges": [],
    }
    if graph.is_multigraph():
        payload["edges"] = [
            (repr(u), repr(v), repr(k), sorted(attrs.items()))
            for u, v, k, attrs in graph.edges(keys=True, data=True)
        ]
    else:
        payload["edges"] = [
            (repr(u), repr(v), sorted(attrs.items()))
            for u, v, attrs in graph.edges(data=True)
        ]
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def run_once(impl: str, scenario: str, n: int, weighted: bool) -> tuple[float, str, int, int]:
    lib = fnx if impl == "fnx" else nx
    start = time.perf_counter()
    graph = construct(lib, scenario, n, weighted=weighted)
    elapsed = time.perf_counter() - start
    return elapsed, digest_graph(graph), graph.number_of_nodes(), graph.number_of_edges()


def bench(args) -> dict:
    samples = []
    digest = None
    nodes = edges = 0
    for _ in range(args.warmup):
        run_once(args.impl, args.scenario, args.n, args.weighted)
    for _ in range(args.runs):
        elapsed, digest, nodes, edges = run_once(args.impl, args.scenario, args.n, args.weighted)
        samples.append(elapsed)
    samples_sorted = sorted(samples)
    return {
        "impl": args.impl,
        "scenario": args.scenario,
        "n": args.n,
        "weighted": args.weighted,
        "runs": args.runs,
        "nodes": nodes,
        "edges": edges,
        "digest": digest,
        "median_s": statistics.median(samples),
        "mean_s": statistics.mean(samples),
        "p95_s": samples_sorted[int(0.95 * (len(samples_sorted) - 1))],
        "min_s": min(samples),
        "max_s": max(samples),
        "samples_s": samples,
    }


def golden(args) -> dict:
    rows = []
    for scenario in args.scenarios:
        fnx_elapsed, fnx_digest, fnx_nodes, fnx_edges = run_once("fnx", scenario, args.n, args.weighted)
        nx_elapsed, nx_digest, nx_nodes, nx_edges = run_once("nx", scenario, args.n, args.weighted)
        rows.append(
            {
                "scenario": scenario,
                "weighted": args.weighted,
                "fnx_digest": fnx_digest,
                "nx_digest": nx_digest,
                "match": fnx_digest == nx_digest,
                "fnx_elapsed_s": fnx_elapsed,
                "nx_elapsed_s": nx_elapsed,
                "fnx_nodes": fnx_nodes,
                "nx_nodes": nx_nodes,
                "fnx_edges": fnx_edges,
                "nx_edges": nx_edges,
            }
        )
    semantic_rows = [
        {
            "scenario": row["scenario"],
            "weighted": row["weighted"],
            "fnx_digest": row["fnx_digest"],
            "nx_digest": row["nx_digest"],
            "match": row["match"],
            "fnx_nodes": row["fnx_nodes"],
            "nx_nodes": row["nx_nodes"],
            "fnx_edges": row["fnx_edges"],
            "nx_edges": row["nx_edges"],
        }
        for row in rows
    ]
    encoded = json.dumps(rows, sort_keys=True, separators=(",", ":")).encode()
    semantic_encoded = json.dumps(
        semantic_rows, sort_keys=True, separators=(",", ":")
    ).encode()
    return {
        "rows": rows,
        "bundle_sha256": hashlib.sha256(encoded).hexdigest(),
        "semantic_bundle_sha256": hashlib.sha256(semantic_encoded).hexdigest(),
    }


def profile(args) -> dict:
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    profile_path = out_dir / f"{args.phase}_{args.impl}_{args.scenario}.prof"
    text_path = out_dir / f"{args.phase}_{args.impl}_{args.scenario}_profile.txt"
    profiler = cProfile.Profile()
    for _ in range(args.warmup):
        run_once(args.impl, args.scenario, args.n, args.weighted)
    profiler.enable()
    for _ in range(args.repeat):
        run_once(args.impl, args.scenario, args.n, args.weighted)
    profiler.disable()
    profiler.dump_stats(profile_path)
    with text_path.open("w", encoding="utf-8") as fh:
        stats = pstats.Stats(profiler, stream=fh).sort_stats("cumtime")
        stats.print_stats(args.limit)
    return {"profile": str(profile_path), "text": str(text_path)}


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)

    bench_parser = sub.add_parser("bench")
    bench_parser.add_argument("--impl", choices=["fnx", "nx"], required=True)
    bench_parser.add_argument("--scenario", required=True)
    bench_parser.add_argument("--n", type=int, default=800)
    bench_parser.add_argument("--runs", type=int, default=25)
    bench_parser.add_argument("--warmup", type=int, default=3)
    bench_parser.add_argument("--weighted", action="store_true")

    golden_parser = sub.add_parser("golden")
    golden_parser.add_argument("--n", type=int, default=120)
    golden_parser.add_argument("--weighted", action="store_true")
    golden_parser.add_argument(
        "--scenarios",
        nargs="+",
        default=[
            "multidigraph_from_graph",
            "multidigraph_from_multigraph",
            "digraph_from_multigraph",
            "multigraph_from_graph",
        ],
    )

    profile_parser = sub.add_parser("profile")
    profile_parser.add_argument("--impl", choices=["fnx", "nx"], required=True)
    profile_parser.add_argument("--scenario", required=True)
    profile_parser.add_argument("--n", type=int, default=800)
    profile_parser.add_argument("--repeat", type=int, default=20)
    profile_parser.add_argument("--warmup", type=int, default=3)
    profile_parser.add_argument("--weighted", action="store_true")
    profile_parser.add_argument("--phase", default="baseline")
    profile_parser.add_argument("--out-dir", default="tests/artifacts/perf/20260614T-k1k74-lazy-edge-attrs")
    profile_parser.add_argument("--limit", type=int, default=30)

    args = parser.parse_args()
    if args.cmd == "bench":
        result = bench(args)
    elif args.cmd == "golden":
        result = golden(args)
    else:
        result = profile(args)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
