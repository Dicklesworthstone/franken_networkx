#!/usr/bin/env python3
"""Bench and parity harness for br-r37-c1-nt3co.

The script is intentionally import-path neutral: set PYTHONPATH to either an
extracted baseline wheel or the candidate package tree before running it.
"""

from __future__ import annotations

import argparse
import cProfile
import hashlib
import json
import pstats
import statistics
import sys
import time
from io import StringIO

import franken_networkx as fnx
import networkx as nx


CASES = ("rgg", "soft", "thresholded", "geometric_edges")


def build_graphs(impl, case: str, n: int, *, seed: int):
    mod = fnx if impl == "fnx" else nx
    if case == "rgg":
        return mod.random_geometric_graph(n, 0.075, seed=seed)
    if case == "soft":
        return mod.soft_random_geometric_graph(n, 0.12, seed=seed)
    if case == "thresholded":
        return mod.thresholded_random_geometric_graph(n, 0.12, 1.0, seed=seed)
    if case == "geometric_edges":
        graph = mod.random_geometric_graph(n, 0.075, seed=seed)
        return mod.geometric_edges(graph, 0.075)
    raise ValueError(case)


def graph_payload(value):
    if isinstance(value, list):
        return {"edges": [list(edge) for edge in value]}
    nodes = [
        [node, {key: attr[key] for key in sorted(attr)}]
        for node, attr in value.nodes(data=True)
    ]
    return {
        "nodes": nodes,
        "edges": [list(edge) for edge in value.edges()],
        "node_count": value.number_of_nodes(),
        "edge_count": value.number_of_edges(),
    }


def digest_payload(payload) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def command_golden(args) -> int:
    rows = []
    for n in args.n_values:
        for seed in args.seeds:
            for case in CASES:
                fnx_payload = graph_payload(build_graphs("fnx", case, n, seed=seed))
                nx_payload = graph_payload(build_graphs("nx", case, n, seed=seed))
                if fnx_payload != nx_payload:
                    print(
                        json.dumps(
                            {
                                "case": case,
                                "n": n,
                                "seed": seed,
                                "fnx_sha": digest_payload(fnx_payload),
                                "nx_sha": digest_payload(nx_payload),
                            },
                            sort_keys=True,
                        ),
                        file=sys.stderr,
                    )
                    return 1
                rows.append(
                    {
                        "case": case,
                        "n": n,
                        "seed": seed,
                        "sha256": digest_payload(fnx_payload),
                    }
                )
    bundle_sha = digest_payload(rows)
    print(json.dumps({"bundle_sha256": bundle_sha, "rows": rows}, sort_keys=True))
    return 0


def command_bench(args) -> int:
    timings = []
    edge_counts = []
    for i in range(args.loops):
        seed = args.seed + i
        start = time.perf_counter()
        value = build_graphs(args.impl, args.case, args.n, seed=seed)
        timings.append(time.perf_counter() - start)
        if isinstance(value, list):
            edge_counts.append(len(value))
        else:
            edge_counts.append(value.number_of_edges())
    print(
        json.dumps(
            {
                "case": args.case,
                "impl": args.impl,
                "n": args.n,
                "loops": args.loops,
                "median_s": statistics.median(timings),
                "mean_s": statistics.fmean(timings),
                "min_s": min(timings),
                "max_s": max(timings),
                "edge_count_sha256": digest_payload(edge_counts),
            },
            sort_keys=True,
        )
    )
    return 0


def command_profile(args) -> int:
    profiler = cProfile.Profile()
    profiler.enable()
    for i in range(args.loops):
        build_graphs("fnx", args.case, args.n, seed=args.seed + i)
    profiler.disable()
    out = StringIO()
    stats = pstats.Stats(profiler, stream=out).sort_stats("cumtime")
    stats.print_stats(args.limit)
    print(out.getvalue())
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)

    golden = sub.add_parser("golden")
    golden.add_argument("--n-values", nargs="+", type=int, default=[80, 240])
    golden.add_argument("--seeds", nargs="+", type=int, default=[7, 19, 123])
    golden.set_defaults(func=command_golden)

    bench = sub.add_parser("bench")
    bench.add_argument("--impl", choices=("fnx", "nx"), required=True)
    bench.add_argument("--case", choices=CASES, required=True)
    bench.add_argument("--n", type=int, default=800)
    bench.add_argument("--seed", type=int, default=12345)
    bench.add_argument("--loops", type=int, default=5)
    bench.set_defaults(func=command_bench)

    profile = sub.add_parser("profile")
    profile.add_argument("--case", choices=CASES, default="soft")
    profile.add_argument("--n", type=int, default=800)
    profile.add_argument("--seed", type=int, default=12345)
    profile.add_argument("--loops", type=int, default=3)
    profile.add_argument("--limit", type=int, default=30)
    profile.set_defaults(func=command_profile)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
