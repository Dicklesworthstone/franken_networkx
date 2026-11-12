#!/usr/bin/env python3
"""Benchmark and proof harness for br-r37-c1-blwqo.

The golden output intentionally records FrankenNetworkX before/after behavior,
not NetworkX equivalence: the Rust generator RNG streams are already documented
as different from NetworkX for some random generators. The contract here is
that the PyGraph bridge change preserves node order, edge order, attrs, and
live attr-dict semantics for generator-built graphs.
"""

from __future__ import annotations

import argparse
import cProfile
import hashlib
import json
import pickle
import copy as copy_module
import pstats
import sys
import time
from pathlib import Path

import franken_networkx as fnx
from franken_networkx import _fnx


def build_case(name: str):
    if name == "empty_500":
        return _fnx.empty_graph(500)
    if name == "path_2000":
        return _fnx.path_graph(2000)
    if name == "complete_180":
        return _fnx.complete_graph(180)
    if name == "gnp_700_006":
        return _fnx.gnp_random_graph(700, 0.06, 7)
    if name == "watts_800_8":
        return _fnx.watts_strogatz_graph(800, 8, 0.2, 7)
    if name == "barabasi_700_4":
        return _fnx.barabasi_albert_graph(700, 4, 7)
    if name == "powerlaw_700_4":
        return _fnx.powerlaw_cluster_graph(700, 4, 0.15, 7)
    raise ValueError(f"unknown case: {name}")


BENCH_CASES = (
    "gnp_700_006",
    "barabasi_700_4",
    "powerlaw_700_4",
    "watts_800_8",
)

GOLDEN_CASES = (
    "empty_500",
    "path_2000",
    "complete_180",
    "gnp_700_006",
    "watts_800_8",
    "barabasi_700_4",
    "powerlaw_700_4",
)


def edge_rows(graph):
    return [[u, v, dict(data)] for u, v, data in graph.edges(data=True)]


def adjacency_rows(graph):
    rows = []
    for node in graph:
        rows.append([node, [[nbr, dict(attrs)] for nbr, attrs in graph[node].items()]])
    return rows


def serialize_graph(name: str):
    graph = build_case(name)
    return {
        "case": name,
        "nodes": [[node, dict(data)] for node, data in graph.nodes(data=True)],
        "edges": edge_rows(graph),
        "adjacency": adjacency_rows(graph),
        "degree": [[node, degree] for node, degree in graph.degree],
        "graph": dict(graph.graph),
        "node_count": graph.number_of_nodes(),
        "edge_count": graph.number_of_edges(),
    }


def golden(args: argparse.Namespace) -> int:
    rows = [serialize_graph(name) for name in GOLDEN_CASES]
    text = "\n".join(json.dumps(row, sort_keys=True, separators=(",", ":")) for row in rows)
    if args.output:
        Path(args.output).write_text(text + "\n", encoding="utf-8")
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    print(digest)
    return 0


def live_attr_check(_: argparse.Namespace) -> int:
    graph = _fnx.path_graph(5)

    node_attrs = graph.nodes[2]
    node_attrs["marker"] = "node-live"
    if graph.nodes[2].get("marker") != "node-live":
        raise AssertionError("node attr dict handout is not live")

    edge_attrs = graph[1][2]
    edge_attrs["weight"] = 3.5
    if graph[2][1].get("weight") != 3.5:
        raise AssertionError("edge attr dict handout is not shared/live")
    if graph.get_edge_data(1, 2).get("weight") != 3.5:
        raise AssertionError("get_edge_data did not return live edge attrs")

    data_edge = next(edge for edge in graph.edges(data=True) if edge[:2] == (1, 2))
    data_edge[2]["from_edges"] = True
    if graph[1][2].get("from_edges") is not True:
        raise AssertionError("edges(data=True) attr dict is not live")

    adj_edge = dict(graph.adjacency())[1][2]
    adj_edge["from_adjacency"] = True
    if graph[1][2].get("from_adjacency") is not True:
        raise AssertionError("adjacency attr dict is not live")

    copied = graph.copy()
    if copied.nodes[2].get("marker") != "node-live":
        raise AssertionError("copy lost materialized node attrs")
    if copied[1][2].get("weight") != 3.5:
        raise AssertionError("copy lost materialized edge attrs")

    sub = graph.subgraph([1, 2, 3])
    if sorted(sub.edges()) != [(1, 2), (2, 3)]:
        raise AssertionError("subgraph lost edges with lazily empty attrs")

    shallow = copy_module.copy(_fnx.path_graph(4))
    if sorted(shallow.edges()) != [(0, 1), (1, 2), (2, 3)]:
        raise AssertionError("copy.copy lost lazily empty generator edges")

    directed = _fnx.path_graph(4).to_directed()
    if sorted(directed.edges()) != [(0, 1), (1, 0), (1, 2), (2, 1), (2, 3), (3, 2)]:
        raise AssertionError("to_directed lost lazily empty generator edges")

    weighted = _fnx.path_graph(4)
    if weighted.size(weight="weight") != 3.0:
        raise AssertionError("size(weight=...) did not default lazy edge attrs to 1")
    if dict(weighted.degree(weight="weight"))[1] != 2:
        raise AssertionError("weighted degree did not default lazy edge attrs to 1")

    restored = pickle.loads(pickle.dumps(_fnx.path_graph(4)))
    if sorted(restored.edges()) != [(0, 1), (1, 2), (2, 3)]:
        raise AssertionError("pickle round trip lost lazily empty generator edges")

    print("live-attr-check ok")
    return 0


def bench(args: argparse.Namespace) -> int:
    case = args.case
    loops = args.loops
    start = time.perf_counter()
    total_nodes = 0
    total_edges = 0
    for _ in range(loops):
        graph = build_case(case)
        total_nodes += graph.number_of_nodes()
        total_edges += graph.number_of_edges()
    elapsed = time.perf_counter() - start
    print(
        json.dumps(
            {
                "case": case,
                "loops": loops,
                "seconds": elapsed,
                "nodes": total_nodes,
                "edges": total_edges,
            },
            sort_keys=True,
        )
    )
    return 0


def profile(args: argparse.Namespace) -> int:
    profiler = cProfile.Profile()
    profiler.enable()
    bench(args)
    profiler.disable()
    stats = pstats.Stats(profiler, stream=sys.stdout).sort_stats("cumulative")
    stats.print_stats(30)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)

    golden_parser = sub.add_parser("golden")
    golden_parser.add_argument("--output")
    golden_parser.set_defaults(func=golden)

    live_parser = sub.add_parser("live-attr-check")
    live_parser.set_defaults(func=live_attr_check)

    bench_parser = sub.add_parser("bench")
    bench_parser.add_argument("--case", choices=BENCH_CASES, required=True)
    bench_parser.add_argument("--loops", type=int, default=40)
    bench_parser.set_defaults(func=bench)

    profile_parser = sub.add_parser("profile")
    profile_parser.add_argument("--case", choices=BENCH_CASES, required=True)
    profile_parser.add_argument("--loops", type=int, default=40)
    profile_parser.set_defaults(func=profile)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
