#!/usr/bin/env python3
"""Profile delegation-heavy wrappers for br-r37-c1-qx7na."""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import time
from collections.abc import Callable
from typing import Any

import franken_networkx as fnx
import networkx as nx


def _stable(obj: Any) -> Any:
    if isinstance(obj, dict):
        return [[_stable(k), _stable(v)] for k, v in obj.items()]
    if isinstance(obj, (list, tuple)):
        return [_stable(value) for value in obj]
    if isinstance(obj, set):
        return sorted(_stable(value) for value in obj)
    if isinstance(obj, float):
        if obj == float("inf"):
            return "inf"
        if obj == float("-inf"):
            return "-inf"
    return f"{type(obj).__name__}:{obj!r}"


def _digest(value: Any) -> str:
    payload = json.dumps(_stable(value), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def _weighted_path(module: Any, n: int) -> Any:
    graph = module.Graph()
    graph.add_weighted_edges_from((i, i + 1, float((i % 7) + 1)) for i in range(n - 1))
    graph.add_weighted_edges_from((i, i + 2, float((i % 5) + 3)) for i in range(n - 2))
    return graph


def _directed_path(module: Any, n: int) -> Any:
    graph = module.DiGraph()
    graph.add_edges_from((i, i + 1) for i in range(n - 1))
    graph.add_edges_from((i, i + 2) for i in range(n - 2))
    return graph


def _cycle_chain(module: Any, n: int) -> Any:
    graph = module.cycle_graph(n)
    graph.add_edges_from((i, (i + 3) % n) for i in range(0, n, 3))
    return graph


def _weighted_dense(module: Any, n: int) -> Any:
    graph = module.Graph()
    for i in range(n):
        graph.add_edge(i, (i + 1) % n, weight=float((i % 11) + 1))
        graph.add_edge(i, (i + 7) % n, weight=float((i % 13) + 2))
    return graph


def build_all_pairs_dijkstra(module: Any, n: int) -> tuple[Any]:
    return (_weighted_path(module, n),)


def case_all_pairs_dijkstra(module: Any, graph: Any) -> Any:
    return list(module.all_pairs_dijkstra(graph, weight="weight"))


def build_average_shortest_path_length(module: Any, n: int) -> tuple[Any]:
    return (_weighted_path(module, n),)


def case_average_shortest_path_length(module: Any, graph: Any) -> Any:
    return module.average_shortest_path_length(graph, weight="weight")


def build_all_shortest_paths(module: Any, n: int) -> tuple[Any, Any, Any]:
    graph = module.grid_2d_graph(n, n)
    return graph, (0, 0), (n - 1, n - 1)


def case_all_shortest_paths(module: Any, graph: Any, source: Any, target: Any) -> Any:
    return list(module.all_shortest_paths(graph, source, target))


def build_group_degree_centrality(module: Any, n: int) -> tuple[Any, set[int]]:
    return _directed_path(module, n), {0, 1, 2}


def case_group_degree_centrality(module: Any, graph: Any, group: set[int]) -> Any:
    return module.group_degree_centrality(graph, group)


def build_chain_decomposition(module: Any, n: int) -> tuple[Any]:
    return (_cycle_chain(module, n),)


def case_chain_decomposition(module: Any, graph: Any) -> Any:
    return list(module.chain_decomposition(graph))


def build_eulerian_path_directed(module: Any, n: int) -> tuple[Any]:
    graph = module.DiGraph()
    graph.add_edges_from((i, i + 1) for i in range(n - 1))
    return (graph,)


def case_eulerian_path_directed(module: Any, graph: Any) -> Any:
    return list(module.eulerian_path(graph))


def build_hyper_wiener_weighted(module: Any, n: int) -> tuple[Any]:
    return (_weighted_dense(module, n),)


def case_hyper_wiener_weighted(module: Any, graph: Any) -> Any:
    return module.hyper_wiener_index(graph, weight="weight")


CASES: dict[str, tuple[Callable[..., tuple[Any, ...]], Callable[..., Any], int]] = {
    "all_pairs_dijkstra_weighted": (
        build_all_pairs_dijkstra,
        case_all_pairs_dijkstra,
        80,
    ),
    "average_shortest_path_length_weighted": (
        build_average_shortest_path_length,
        case_average_shortest_path_length,
        120,
    ),
    "all_shortest_paths_grid": (
        build_all_shortest_paths,
        case_all_shortest_paths,
        8,
    ),
    "group_degree_centrality_directed": (
        build_group_degree_centrality,
        case_group_degree_centrality,
        600,
    ),
    "chain_decomposition": (
        build_chain_decomposition,
        case_chain_decomposition,
        250,
    ),
    "eulerian_path_directed": (
        build_eulerian_path_directed,
        case_eulerian_path_directed,
        2_000,
    ),
    "hyper_wiener_weighted": (
        build_hyper_wiener_weighted,
        case_hyper_wiener_weighted,
        60,
    ),
}


def _run_once(module: Any, case: str, inputs: tuple[Any, ...]) -> tuple[float, str, Any]:
    _, func, _ = CASES[case]
    started = time.perf_counter()
    value = func(module, *inputs)
    elapsed = time.perf_counter() - started
    return elapsed, _digest(value), value


def bench(args: argparse.Namespace) -> None:
    selected = list(CASES) if args.case == "all" else [args.case]
    impls = (("fnx", fnx), ("nx", nx)) if args.impl == "both" else ((args.impl, fnx if args.impl == "fnx" else nx),)
    for case in selected:
        records = []
        for impl, module in impls:
            build, _, default_size = CASES[case]
            inputs = build(module, args.size or default_size)
            samples = []
            digest = ""
            for _ in range(args.repeats):
                elapsed, digest, _ = _run_once(module, case, inputs)
                samples.append(elapsed)
            records.append(
                {
                    "impl": impl,
                    "case": case,
                    "size": args.size or CASES[case][2],
                    "repeats": args.repeats,
                    "mean_sec": statistics.fmean(samples),
                    "median_sec": statistics.median(samples),
                    "min_sec": min(samples),
                    "max_sec": max(samples),
                    "samples_sec": samples,
                    "digest": digest,
                }
            )
        fnx_record = records[0] if records[0]["impl"] == "fnx" else None
        nx_record = next((record for record in records if record["impl"] == "nx"), None)
        print(
            json.dumps(
                {
                    "case": case,
                    "records": records,
                    "fnx_over_nx": (
                        fnx_record["mean_sec"] / nx_record["mean_sec"]
                        if fnx_record is not None and nx_record is not None
                        else None
                    ),
                    "digests_match": (
                        fnx_record["digest"] == nx_record["digest"]
                        if fnx_record is not None and nx_record is not None
                        else None
                    ),
                },
                sort_keys=True,
                separators=(",", ":"),
            ),
            flush=True,
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", choices=[*CASES, "all"], default="all")
    parser.add_argument("--impl", choices=["both", "fnx", "nx"], default="both")
    parser.add_argument("--size", type=int, default=0)
    parser.add_argument("--repeats", type=int, default=5)
    args = parser.parse_args()
    bench(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
