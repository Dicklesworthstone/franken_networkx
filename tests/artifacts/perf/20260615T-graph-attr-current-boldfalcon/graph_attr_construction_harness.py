#!/usr/bin/env python3
"""Focused Graph attributed add_edges_from benchmark/proof harness."""

from __future__ import annotations

import argparse
import cProfile
import hashlib
import hmac
import json
import pstats
import random
import statistics
import time
from pathlib import Path

import franken_networkx as fnx
import networkx as nx


NODE_COUNT = 2000
EDGE_COUNT = 8000
SEED = 2


def make_edges() -> list[tuple[int, int, dict[str, float]]]:
    rng = random.Random(SEED)
    return [
        (rng.randrange(NODE_COUNT), rng.randrange(NODE_COUNT), {"weight": 1.0})
        for _ in range(EDGE_COUNT)
    ]


EDGES = make_edges()


def build_graph(impl: str):
    cls = fnx.Graph if impl == "fnx" else nx.Graph
    graph = cls()
    graph.add_edges_from(EDGES)
    return graph


def signature(graph) -> dict[str, object]:
    return {
        "nodes": list(graph.nodes()),
        "edges": [
            [u, v, sorted(data.items())]
            for u, v, data in graph.edges(data=True)
        ],
    }


def attr_semantics(impl: str) -> dict[str, object]:
    cls = fnx.Graph if impl == "fnx" else nx.Graph
    graph = cls()
    first = {"weight": 1.0, "label": "first"}
    duplicate = {"weight": 3.0, "extra": "last"}
    graph.add_edges_from([(1, 2, first), (2, 3, {"kind": "x"}), (1, 2, duplicate)])
    before_source_mutation = signature(graph)

    first["weight"] = 99.0
    duplicate["extra"] = "mutated"
    after_source_mutation = signature(graph)

    graph.nodes[1]["color"] = "red"
    graph.nodes[2]["rank"] = 7
    graph[1][2]["edge_edit"] = "ok"
    after_view_mutation = signature(graph)

    graph.add_edge(3, 3, loop=True)
    graph.add_edge(3, 4, weight=2.0)
    after_more_edges = signature(graph)

    return {
        "before_source_mutation": before_source_mutation,
        "after_source_mutation": after_source_mutation,
        "after_view_mutation": after_view_mutation,
        "after_more_edges": after_more_edges,
    }


def payload_bytes(payload: object) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()


def digest_payload(payload: object) -> str:
    return hashlib.sha256(payload_bytes(payload)).hexdigest()


def payloads_match(left: object, right: object) -> bool:
    return hmac.compare_digest(payload_bytes(left), payload_bytes(right))


def bench_impl(impl: str, repeats: int) -> dict[str, object]:
    samples = []
    marker = None
    for _ in range(repeats):
        start = time.perf_counter()
        graph = build_graph(impl)
        elapsed = time.perf_counter() - start
        marker = [graph.number_of_nodes(), graph.number_of_edges()]
        samples.append(elapsed)
    return {
        "impl": impl,
        "node_count": NODE_COUNT,
        "edge_count": EDGE_COUNT,
        "repeats": repeats,
        "min_s": min(samples),
        "median_s": statistics.median(samples),
        "mean_s": statistics.mean(samples),
        "max_s": max(samples),
        "samples_s": samples,
        "marker": marker,
    }


def run_once(impl: str, loops: int) -> None:
    marker = None
    for _ in range(loops):
        graph = build_graph(impl)
        marker = [graph.number_of_nodes(), graph.number_of_edges()]
    print(json.dumps({"impl": impl, "loops": loops, "marker": marker}, sort_keys=True))


def write_profile(impl: str, loops: int, output: Path) -> None:
    profiler = cProfile.Profile()
    profiler.enable()
    marker = None
    for _ in range(loops):
        graph = build_graph(impl)
        marker = [graph.number_of_nodes(), graph.number_of_edges()]
    profiler.disable()
    with output.open("w", encoding="utf-8") as handle:
        handle.write(f"marker={marker}\n")
        stats = pstats.Stats(profiler, stream=handle).sort_stats("cumtime")
        stats.print_stats(25)


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="mode", required=True)

    golden = sub.add_parser("golden")
    golden.add_argument("--output", type=Path, required=True)

    semantics = sub.add_parser("semantics")
    semantics.add_argument("--output", type=Path, required=True)

    bench = sub.add_parser("bench")
    bench.add_argument("--impl", choices=["fnx", "nx"], required=True)
    bench.add_argument("--repeats", type=int, default=17)
    bench.add_argument("--output", type=Path, required=True)

    once = sub.add_parser("once")
    once.add_argument("--impl", choices=["fnx", "nx"], required=True)
    once.add_argument("--loops", type=int, default=30)

    profile = sub.add_parser("profile")
    profile.add_argument("--impl", choices=["fnx", "nx"], required=True)
    profile.add_argument("--loops", type=int, default=120)
    profile.add_argument("--output", type=Path, required=True)

    args = parser.parse_args()

    if args.mode == "golden":
        nx_payload = signature(build_graph("nx"))
        fnx_payload = signature(build_graph("fnx"))
        payload = {
            "nx_digest": digest_payload(nx_payload),
            "fnx_digest": digest_payload(fnx_payload),
            "digests_match": payloads_match(nx_payload, fnx_payload),
            "nx": nx_payload,
            "fnx": fnx_payload,
        }
        args.output.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")
        return 0 if payload["digests_match"] else 1

    if args.mode == "semantics":
        nx_payload = attr_semantics("nx")
        fnx_payload = attr_semantics("fnx")
        payload = {
            "nx_digest": digest_payload(nx_payload),
            "fnx_digest": digest_payload(fnx_payload),
            "digests_match": payloads_match(nx_payload, fnx_payload),
            "nx": nx_payload,
            "fnx": fnx_payload,
        }
        args.output.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")
        return 0 if payload["digests_match"] else 1

    if args.mode == "bench":
        args.output.write_text(
            json.dumps(bench_impl(args.impl, args.repeats), sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return 0

    if args.mode == "once":
        run_once(args.impl, args.loops)
        return 0

    if args.mode == "profile":
        write_profile(args.impl, args.loops, args.output)
        return 0

    raise AssertionError(args.mode)


if __name__ == "__main__":
    raise SystemExit(main())
