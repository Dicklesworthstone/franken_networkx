#!/usr/bin/env python3
"""Current-head algorithm residual sweep."""

from __future__ import annotations

import argparse
import cProfile
import hashlib
import io
import json
import pstats
import statistics
import time
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any, Callable

import franken_networkx as fnx
import networkx as nx


@dataclass
class Scenario:
    name: str
    nx_fn: Callable[[], Any]
    fnx_fn: Callable[[], Any]
    runs: int = 7
    warmup: int = 2


def _stable(value: Any) -> Any:
    if hasattr(value, "nodes") and hasattr(value, "edges"):
        return {
            "nodes": list(value.nodes(data=True)),
            "edges": list(value.edges(data=True)),
        }
    if isinstance(value, dict):
        return [[_stable(k), _stable(v)] for k, v in value.items()]
    if isinstance(value, set | frozenset):
        return sorted(_stable(item) for item in value)
    if isinstance(value, tuple):
        return [_stable(item) for item in value]
    if isinstance(value, list):
        return [_stable(item) for item in value]
    if isinstance(value, float):
        return repr(value)
    return value


def _materialize(value: Any) -> Any:
    if isinstance(value, (str, bytes, dict, list, tuple, set, frozenset)):
        return value
    if isinstance(value, Iterable) and not hasattr(value, "nodes"):
        return list(value)
    return value


def _digest(value: Any) -> str:
    raw = json.dumps(_stable(_materialize(value)), sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def _build_scenarios() -> list[Scenario]:
    g_ba_1200_nx = nx.barabasi_albert_graph(1200, 4, seed=11)
    g_ba_1200_fnx = fnx.barabasi_albert_graph(1200, 4, seed=11)
    g_ba_2500_nx = nx.barabasi_albert_graph(2500, 4, seed=12)
    g_ba_2500_fnx = fnx.barabasi_albert_graph(2500, 4, seed=12)
    g_ws_1500_nx = nx.watts_strogatz_graph(1500, 6, 0.25, seed=13)
    g_ws_1500_fnx = fnx.watts_strogatz_graph(1500, 6, 0.25, seed=13)
    g_er_1200_nx = nx.erdos_renyi_graph(1200, 0.006, seed=14)
    g_er_1200_fnx = fnx.erdos_renyi_graph(1200, 0.006, seed=14)

    dag_edges = [
        (u, v)
        for u in range(450)
        for v in range(u + 1, min(450, u + 9))
        if (u * 17 + v) % 5 != 0
    ]
    dag_nx = nx.DiGraph()
    dag_nx.add_nodes_from(range(450))
    dag_nx.add_edges_from(dag_edges)
    dag_fnx = fnx.DiGraph()
    dag_fnx.add_nodes_from(range(450))
    dag_fnx.add_edges_from(dag_edges)

    return [
        Scenario("degree_centrality_ba2500", lambda: nx.degree_centrality(g_ba_2500_nx), lambda: fnx.degree_centrality(g_ba_2500_fnx)),
        Scenario("closeness_centrality_ba1200", lambda: nx.closeness_centrality(g_ba_1200_nx), lambda: fnx.closeness_centrality(g_ba_1200_fnx), 4, 1),
        Scenario("shortest_path_pair_ba1200", lambda: nx.shortest_path(g_ba_1200_nx, 0, 900), lambda: fnx.shortest_path(g_ba_1200_fnx, 0, 900)),
        Scenario("dijkstra_path_pair_ba1200", lambda: nx.dijkstra_path(g_ba_1200_nx, 0, 900), lambda: fnx.dijkstra_path(g_ba_1200_fnx, 0, 900)),
        Scenario("bfs_edges_ba1200", lambda: list(nx.bfs_edges(g_ba_1200_nx, 0)), lambda: list(fnx.bfs_edges(g_ba_1200_fnx, 0))),
        Scenario("dfs_edges_ba1200", lambda: list(nx.dfs_edges(g_ba_1200_nx, 0)), lambda: list(fnx.dfs_edges(g_ba_1200_fnx, 0))),
        Scenario("connected_components_er1200", lambda: list(nx.connected_components(g_er_1200_nx)), lambda: list(fnx.connected_components(g_er_1200_fnx))),
        Scenario("is_connected_ba2500", lambda: nx.is_connected(g_ba_2500_nx), lambda: fnx.is_connected(g_ba_2500_fnx)),
        Scenario("core_number_ba1200", lambda: nx.core_number(g_ba_1200_nx), lambda: fnx.core_number(g_ba_1200_fnx)),
        Scenario("pagerank_ba1200", lambda: nx.pagerank(g_ba_1200_nx), lambda: fnx.pagerank(g_ba_1200_fnx), 4, 1),
        Scenario("average_clustering_ws1500", lambda: nx.average_clustering(g_ws_1500_nx), lambda: fnx.average_clustering(g_ws_1500_fnx), 5, 1),
        Scenario("transitivity_ws1500", lambda: nx.transitivity(g_ws_1500_nx), lambda: fnx.transitivity(g_ws_1500_fnx)),
        Scenario("all_pairs_lca_dag450", lambda: list(nx.all_pairs_lowest_common_ancestor(dag_nx)), lambda: list(fnx.all_pairs_lowest_common_ancestor(dag_fnx)), 4, 1),
        Scenario("topological_sort_dag450", lambda: list(nx.topological_sort(dag_nx)), lambda: list(fnx.topological_sort(dag_fnx))),
        Scenario("ancestors_dag450", lambda: nx.ancestors(dag_nx, 449), lambda: fnx.ancestors(dag_fnx, 449)),
        Scenario("descendants_dag450", lambda: nx.descendants(dag_nx, 0), lambda: fnx.descendants(dag_fnx, 0)),
    ]


def _measure(fn: Callable[[], Any], runs: int, warmup: int) -> dict[str, Any]:
    for _ in range(warmup):
        _materialize(fn())
    samples = []
    digest = ""
    for _ in range(runs):
        start = time.perf_counter()
        value = _materialize(fn())
        samples.append(time.perf_counter() - start)
        digest = _digest(value)
    return {
        "best_s": min(samples),
        "digest": digest,
        "mean_s": statistics.fmean(samples),
        "median_s": statistics.median(samples),
        "samples_s": samples,
    }


def command_sweep(args: argparse.Namespace) -> int:
    rows = []
    for scenario in _build_scenarios():
        nx_stats = _measure(scenario.nx_fn, scenario.runs, scenario.warmup)
        fnx_stats = _measure(scenario.fnx_fn, scenario.runs, scenario.warmup)
        rows.append(
            {
                "name": scenario.name,
                "digests_match": nx_stats["digest"] == fnx_stats["digest"],
                "fnx": fnx_stats,
                "median_ratio_fnx_over_nx": fnx_stats["median_s"] / nx_stats["median_s"],
                "nx": nx_stats,
            }
        )
    rows.sort(key=lambda row: row["median_ratio_fnx_over_nx"], reverse=True)
    print(json.dumps({"rows": rows}, sort_keys=True))
    return 0


def command_profile(args: argparse.Namespace) -> int:
    scenarios = {scenario.name: scenario for scenario in _build_scenarios()}
    scenario = scenarios[args.name]
    profiler = cProfile.Profile()
    profiler.enable()
    for _ in range(args.repeats):
        value = _materialize(scenario.fnx_fn())
    profiler.disable()
    stream = io.StringIO()
    pstats.Stats(profiler, stream=stream).strip_dirs().sort_stats("cumtime").print_stats(args.limit)
    print("name=" + args.name + " sha256=" + _digest(value) + "\n" + stream.getvalue())
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("sweep").set_defaults(func=command_sweep)

    profile = sub.add_parser("profile")
    profile.add_argument("name")
    profile.add_argument("--repeats", type=int, default=5)
    profile.add_argument("--limit", type=int, default=40)
    profile.set_defaults(func=command_profile)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
