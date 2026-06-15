#!/usr/bin/env python3
"""Graph attributed-edge construction residual harness for br-r37-c1-04z53.9104."""

from __future__ import annotations

import argparse
import cProfile
import hashlib
import json
import pstats
import random
import statistics
import time
from io import StringIO
from typing import Any

import franken_networkx as fnx
import networkx as nx


NODE_COUNT = 2000
EDGE_COUNT = 8000
SEED = 20260615


def make_edges() -> list[tuple[int, int, dict[str, float]]]:
    rng = random.Random(SEED)
    return [
        (rng.randrange(NODE_COUNT), rng.randrange(NODE_COUNT), {"weight": 1.0})
        for _ in range(EDGE_COUNT)
    ]


EDGES = make_edges()


def edge_key(u: int, v: int) -> tuple[int, int]:
    return (u, v) if u <= v else (v, u)


def duplicate_probe() -> tuple[int, int]:
    seen: set[tuple[int, int]] = set()
    for u, v, _ in EDGES:
        key = edge_key(u, v)
        if key in seen:
            return key
        seen.add(key)
    raise RuntimeError("workload unexpectedly has no duplicate edge")


DUPLICATE_EDGE = duplicate_probe()


def build_graph(impl: str) -> Any:
    mod = fnx if impl == "fnx" else nx
    graph = mod.Graph()
    graph.add_edges_from(EDGES)
    return graph


def graph_payload(graph: Any) -> dict[str, Any]:
    duplicate_attrs = graph.get_edge_data(*DUPLICATE_EDGE)
    return {
        "nodes": list(graph.nodes()),
        "edges": [(u, v, sorted(data.items())) for u, v, data in graph.edges(data=True)],
        "adjacency_prefix": {
            str(node): list(graph.adj[node])[:12] for node in list(graph.nodes())[:12]
        },
        "degree_prefix": [(node, graph.degree[node]) for node in list(graph.nodes())[:24]],
        "duplicate_edge": list(DUPLICATE_EDGE),
        "duplicate_attrs": sorted(duplicate_attrs.items()) if duplicate_attrs else None,
        "node_count": graph.number_of_nodes(),
        "edge_count": graph.number_of_edges(),
    }


def digest_payload(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def command_golden(args: argparse.Namespace) -> int:
    fnx_payload = graph_payload(build_graph("fnx"))
    nx_payload = graph_payload(build_graph("nx"))
    payload = {
        "case": "graph_attr_edges_exact_int",
        "edge_count_input": EDGE_COUNT,
        "node_count_input": NODE_COUNT,
        "seed": SEED,
        "fnx": fnx_payload,
        "nx": nx_payload,
        "digests": {
            "fnx": digest_payload(fnx_payload),
            "nx": digest_payload(nx_payload),
        },
    }
    payload["digests_match"] = payload["digests"]["fnx"] == payload["digests"]["nx"]
    payload["snapshots_match"] = fnx_payload == nx_payload
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    if args.out:
        with open(args.out, "w", encoding="utf-8") as handle:
            handle.write(raw + "\n")
    print(raw)
    return 0 if payload["snapshots_match"] else 1


def command_bench(args: argparse.Namespace) -> int:
    samples = []
    payload_digest = None
    for _ in range(args.repeats):
        start = time.perf_counter()
        graph = build_graph(args.impl)
        samples.append(time.perf_counter() - start)
        payload_digest = digest_payload(graph_payload(graph))
    result = {
        "case": "graph_attr_edges_exact_int",
        "impl": args.impl,
        "edge_count_input": EDGE_COUNT,
        "node_count_input": NODE_COUNT,
        "seed": SEED,
        "digest": payload_digest,
        "max_sec": max(samples),
        "mean_sec": statistics.fmean(samples),
        "median_sec": statistics.median(samples),
        "min_sec": min(samples),
        "repeats": args.repeats,
        "samples_sec": samples,
    }
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


def command_once(args: argparse.Namespace) -> int:
    payload = graph_payload(build_graph(args.impl))
    print(digest_payload(payload))
    return 0


def command_profile(args: argparse.Namespace) -> int:
    profiler = cProfile.Profile()
    profiler.enable()
    graph = None
    for _ in range(args.repeats):
        graph = build_graph("fnx")
    profiler.disable()
    out = StringIO()
    pstats.Stats(profiler, stream=out).sort_stats("cumtime").print_stats(args.limit)
    payload = graph_payload(graph)
    print(
        "case=graph_attr_edges_exact_int"
        + " sha256="
        + digest_payload(payload)
        + "\n"
        + out.getvalue()
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)

    golden = sub.add_parser("golden")
    golden.add_argument("--out")
    golden.set_defaults(func=command_golden)

    bench = sub.add_parser("bench")
    bench.add_argument("impl", choices=("fnx", "nx"))
    bench.add_argument("--repeats", type=int, default=13)
    bench.set_defaults(func=command_bench)

    once = sub.add_parser("once")
    once.add_argument("impl", choices=("fnx", "nx"))
    once.set_defaults(func=command_once)

    profile = sub.add_parser("profile")
    profile.add_argument("--repeats", type=int, default=120)
    profile.add_argument("--limit", type=int, default=35)
    profile.set_defaults(func=command_profile)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
