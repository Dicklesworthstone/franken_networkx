#!/usr/bin/env python3
"""Current-head construction residual survey after Graph/DiGraph attr keeps."""

from __future__ import annotations

import argparse
import cProfile
import hashlib
import json
import pstats
import statistics
import time
from pathlib import Path
from typing import Any, Callable

import networkx as nx

import franken_networkx as fnx


def _int_edges(size: int) -> list[tuple[int, int]]:
    return [(i % (size // 4), (i * 17 + 11) % (size // 3 + 17)) for i in range(size)]


def _attr_edges(size: int) -> list[tuple[int, int, dict[str, float]]]:
    return [(u, v, {"weight": 1.0}) for u, v in _int_edges(size)]


def _digest_graph(graph: Any) -> str:
    nodes = [(repr(node), sorted((str(key), repr(value)) for key, value in attrs.items())) for node, attrs in graph.nodes(data=True)]
    if graph.is_multigraph():
        edges = [
            (
                repr(u),
                repr(v),
                repr(key),
                sorted((str(attr_key), repr(value)) for attr_key, value in attrs.items()),
            )
            for u, v, key, attrs in graph.edges(keys=True, data=True)
        ]
    else:
        edges = [
            (
                repr(u),
                repr(v),
                sorted((str(attr_key), repr(value)) for attr_key, value in attrs.items()),
            )
            for u, v, attrs in graph.edges(data=True)
        ]
    payload = json.dumps({"nodes": nodes, "edges": edges}, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def _graph_plain(module: Any, size: int) -> Any:
    graph = module.Graph()
    graph.add_edges_from(_int_edges(size))
    return graph


def _graph_attr(module: Any, size: int) -> Any:
    graph = module.Graph()
    graph.add_edges_from(_attr_edges(size))
    return graph


def _digraph_attr(module: Any, size: int) -> Any:
    graph = module.DiGraph()
    graph.add_edges_from(_attr_edges(size))
    return graph


def _multigraph_attr(module: Any, size: int) -> Any:
    graph = module.MultiGraph()
    graph.add_edges_from(_attr_edges(size))
    return graph


def _multidigraph_attr(module: Any, size: int) -> Any:
    graph = module.MultiDiGraph()
    graph.add_edges_from(_attr_edges(size))
    return graph


CASES: dict[str, tuple[Callable[[Any, int], Any], int]] = {
    "graph_plain": (_graph_plain, 50_000),
    "graph_attr": (_graph_attr, 8_000),
    "digraph_attr": (_digraph_attr, 8_000),
    "multigraph_attr": (_multigraph_attr, 8_000),
    "multidigraph_attr": (_multidigraph_attr, 8_000),
}


def _module(name: str) -> Any:
    if name == "fnx":
        return fnx
    if name == "nx":
        return nx
    raise ValueError(name)


def _measure_case(case: str, impl: str, repeats: int) -> dict[str, Any]:
    builder, size = CASES[case]
    module = _module(impl)
    samples = []
    digest = ""
    node_count = 0
    edge_count = 0
    for _ in range(repeats):
        start = time.perf_counter()
        graph = builder(module, size)
        elapsed = time.perf_counter() - start
        samples.append(elapsed)
        digest = _digest_graph(graph)
        node_count = graph.number_of_nodes()
        edge_count = graph.number_of_edges()
    return {
        "case": case,
        "impl": impl,
        "size": size,
        "nodes": node_count,
        "edges": edge_count,
        "digest": digest,
        "repeats": repeats,
        "samples_s": samples,
        "median_s": statistics.median(samples),
        "mean_s": statistics.fmean(samples),
        "min_s": min(samples),
        "max_s": max(samples),
    }


def survey(args: argparse.Namespace) -> None:
    rows = []
    for case in CASES:
        fnx_result = _measure_case(case, "fnx", args.repeats)
        nx_result = _measure_case(case, "nx", args.repeats)
        rows.append(
            {
                "case": case,
                "digests_match": fnx_result["digest"] == nx_result["digest"],
                "fnx_over_nx": fnx_result["median_s"] / nx_result["median_s"],
                "records": [fnx_result, nx_result],
            }
        )
    print(json.dumps({"impl": "post-graph-attr current-head construction survey", "rows": rows}, indent=2, sort_keys=True))


def once(args: argparse.Namespace) -> None:
    for _ in range(args.loops):
        _measure_case(args.case, args.impl, 1)


def profile(args: argparse.Namespace) -> None:
    profiler = cProfile.Profile()
    profiler.enable()
    once(args)
    profiler.disable()
    stats_path = Path(args.output)
    with stats_path.open("w", encoding="utf-8") as handle:
        pstats.Stats(profiler, stream=handle).strip_dirs().sort_stats("cumulative").print_stats(args.limit)


def main() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="cmd", required=True)

    survey_parser = subparsers.add_parser("survey")
    survey_parser.add_argument("--repeats", type=int, default=9)
    survey_parser.set_defaults(func=survey)

    once_parser = subparsers.add_parser("once")
    once_parser.add_argument("--case", choices=sorted(CASES), required=True)
    once_parser.add_argument("--impl", choices=("fnx", "nx"), required=True)
    once_parser.add_argument("--loops", type=int, default=1)
    once_parser.set_defaults(func=once)

    profile_parser = subparsers.add_parser("profile")
    profile_parser.add_argument("--case", choices=sorted(CASES), required=True)
    profile_parser.add_argument("--impl", choices=("fnx", "nx"), required=True)
    profile_parser.add_argument("--loops", type=int, default=80)
    profile_parser.add_argument("--limit", type=int, default=25)
    profile_parser.add_argument("--output", required=True)
    profile_parser.set_defaults(func=profile)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
