#!/usr/bin/env python3
"""Fresh post-db0qr FNX-vs-NetworkX residual sweep."""

from __future__ import annotations

import cProfile
import io
import json
import pstats
import statistics
import time
from dataclasses import dataclass

import franken_networkx as fnx
import networkx as real_nx


class GenuineNX:
    def __init__(self, nx_module):
        self._nx = nx_module

    def __getattr__(self, name):
        fn = getattr(self._nx, name)
        genuine = getattr(fn, "orig_func", fn)

        def call(*args, **kwargs):
            try:
                return genuine(*args, **kwargs)
            except Exception:
                return fn(*args, **kwargs)

        return call


nx = GenuineNX(real_nx)


@dataclass
class Scenario:
    name: str
    nx_fn: object
    fnx_fn: object
    runs: int = 7
    warmup: int = 2


def measure(fn, runs: int, warmup: int):
    for _ in range(warmup):
        fn()
    times = []
    for _ in range(runs):
        start = time.perf_counter()
        value = fn()
        elapsed = time.perf_counter() - start
        if hasattr(value, "__iter__") and not isinstance(value, (dict, list, tuple, set, str, bytes)):
            value = list(value)
        times.append(elapsed)
    return {
        "best_s": min(times),
        "median_s": statistics.median(times),
        "mean_s": statistics.mean(times),
        "times_s": times,
    }


def profile_text(fn):
    profiler = cProfile.Profile()
    profiler.enable()
    fn()
    profiler.disable()
    stream = io.StringIO()
    pstats.Stats(profiler, stream=stream).strip_dirs().sort_stats("cumtime").print_stats(30)
    return stream.getvalue()


def build_scenarios():
    g_ba_1200_nx = real_nx.barabasi_albert_graph(1200, 4, seed=11)
    g_ba_1200_fnx = fnx.barabasi_albert_graph(1200, 4, seed=11)
    g_ba_2500_nx = real_nx.barabasi_albert_graph(2500, 4, seed=12)
    g_ba_2500_fnx = fnx.barabasi_albert_graph(2500, 4, seed=12)
    g_ws_1500_nx = real_nx.watts_strogatz_graph(1500, 6, 0.25, seed=13)
    g_ws_1500_fnx = fnx.watts_strogatz_graph(1500, 6, 0.25, seed=13)
    g_er_1200_nx = real_nx.erdos_renyi_graph(1200, 0.006, seed=14)
    g_er_1200_fnx = fnx.erdos_renyi_graph(1200, 0.006, seed=14)
    dag_nx = real_nx.DiGraph()
    dag_nx.add_nodes_from(range(450))
    dag_edges = [(u, v) for u in range(450) for v in range(u + 1, min(450, u + 9)) if (u * 17 + v) % 5 != 0]
    dag_nx.add_edges_from(dag_edges)
    dag_fnx = fnx.DiGraph()
    dag_fnx.add_nodes_from(range(450))
    dag_fnx.add_edges_from(dag_edges)

    return [
        Scenario("degree_centrality_ba2500", lambda: nx.degree_centrality(g_ba_2500_nx), lambda: fnx.degree_centrality(g_ba_2500_fnx)),
        Scenario("closeness_centrality_ba1200", lambda: nx.closeness_centrality(g_ba_1200_nx), lambda: fnx.closeness_centrality(g_ba_1200_fnx), runs=4, warmup=1),
        Scenario("shortest_path_length_pair_ba1200", lambda: nx.shortest_path_length(g_ba_1200_nx, 0, 900), lambda: fnx.shortest_path_length(g_ba_1200_fnx, 0, 900)),
        Scenario("dijkstra_path_pair_ba1200", lambda: nx.dijkstra_path(g_ba_1200_nx, 0, 900), lambda: fnx.dijkstra_path(g_ba_1200_fnx, 0, 900)),
        Scenario("bfs_edges_ba1200", lambda: list(nx.bfs_edges(g_ba_1200_nx, 0)), lambda: list(fnx.bfs_edges(g_ba_1200_fnx, 0))),
        Scenario("dfs_edges_ba1200", lambda: list(nx.dfs_edges(g_ba_1200_nx, 0)), lambda: list(fnx.dfs_edges(g_ba_1200_fnx, 0))),
        Scenario("connected_components_er1200", lambda: list(nx.connected_components(g_er_1200_nx)), lambda: list(fnx.connected_components(g_er_1200_fnx))),
        Scenario("is_connected_ba2500", lambda: nx.is_connected(g_ba_2500_nx), lambda: fnx.is_connected(g_ba_2500_fnx)),
        Scenario("core_number_ba1200", lambda: nx.core_number(g_ba_1200_nx), lambda: fnx.core_number(g_ba_1200_fnx)),
        Scenario("pagerank_ba1200", lambda: nx.pagerank(g_ba_1200_nx), lambda: fnx.pagerank(g_ba_1200_fnx), runs=4, warmup=1),
        Scenario("average_clustering_ws1500", lambda: nx.average_clustering(g_ws_1500_nx), lambda: fnx.average_clustering(g_ws_1500_fnx), runs=5, warmup=1),
        Scenario("transitivity_ws1500", lambda: nx.transitivity(g_ws_1500_nx), lambda: fnx.transitivity(g_ws_1500_fnx)),
        Scenario("all_pairs_lca_dag450", lambda: list(nx.all_pairs_lowest_common_ancestor(dag_nx)), lambda: list(fnx.all_pairs_lowest_common_ancestor(dag_fnx)), runs=4, warmup=1),
        Scenario("topological_sort_dag450", lambda: list(nx.topological_sort(dag_nx)), lambda: list(fnx.topological_sort(dag_fnx))),
        Scenario("ancestors_dag450", lambda: nx.ancestors(dag_nx, 449), lambda: fnx.ancestors(dag_fnx, 449)),
        Scenario("descendants_dag450", lambda: nx.descendants(dag_nx, 0), lambda: fnx.descendants(dag_fnx, 0)),
    ]


def main():
    rows = []
    scenario_map = {}
    for scenario in build_scenarios():
        nx_stats = measure(scenario.nx_fn, scenario.runs, scenario.warmup)
        fnx_stats = measure(scenario.fnx_fn, scenario.runs, scenario.warmup)
        row = {
            "name": scenario.name,
            "nx": nx_stats,
            "fnx": fnx_stats,
            "best_ratio_fnx_over_nx": fnx_stats["best_s"] / nx_stats["best_s"],
            "median_ratio_fnx_over_nx": fnx_stats["median_s"] / nx_stats["median_s"],
        }
        rows.append(row)
        scenario_map[scenario.name] = scenario
    rows.sort(key=lambda row: row["best_ratio_fnx_over_nx"], reverse=True)
    top = rows[0]
    payload = {"rows": rows, "top_slower": top}
    print(json.dumps(payload, indent=2, sort_keys=True))
    with open("tests/artifacts/perf/20260611T-post-db0qr-residual-blackthrush/residual_sweep.json", "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, sort_keys=True)
        fh.write("\n")
    top_name = top["name"]
    with open("tests/artifacts/perf/20260611T-post-db0qr-residual-blackthrush/top_profile.txt", "w", encoding="utf-8") as fh:
        fh.write(profile_text(scenario_map[top_name].fnx_fn))


if __name__ == "__main__":
    main()
