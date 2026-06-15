#!/usr/bin/env python3
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


SOURCE = 0
TARGET = 899


def build_graphs():
    base = nx.barabasi_albert_graph(900, 4, seed=4242)
    weighted_edges = []
    for u, v in base.edges():
        weight = ((u * 17 + v * 31) % 9) + 1
        weighted_edges.append((u, v, {"weight": weight}))
    gn = nx.Graph()
    gn.add_nodes_from(base.nodes())
    gn.add_edges_from(weighted_edges)
    gf = fnx.Graph()
    gf.add_nodes_from(base.nodes())
    gf.add_edges_from(weighted_edges)
    return gf, gn


def predecessor_and_distance(module, graph):
    return module.dijkstra_predecessor_and_distance(
        graph, SOURCE, weight="weight",
    )


CASES = {
    "dijkstra_path_length": lambda module, graph: module.dijkstra_path_length(
        graph, SOURCE, TARGET, weight="weight",
    ),
    "shortest_path_length": lambda module, graph: module.shortest_path_length(
        graph, SOURCE, TARGET, weight="weight",
    ),
    "single_source_dijkstra": lambda module, graph: module.single_source_dijkstra(
        graph, SOURCE, weight="weight",
    ),
    "dijkstra_predecessor_and_distance": predecessor_and_distance,
}


def normalize(value):
    if isinstance(value, dict):
        return {
            "__dict__": [
                [repr(key), type(key).__name__, normalize(item)]
                for key, item in value.items()
            ],
        }
    if isinstance(value, tuple):
        return {"__tuple__": [normalize(item) for item in value]}
    if isinstance(value, list):
        return {
            "__list__": [
                [repr(item), type(item).__name__]
                if not isinstance(item, (dict, tuple, list))
                else normalize(item)
                for item in value
            ],
        }
    return {"repr": repr(value), "type": type(value).__name__}


def collect_golden():
    gf, gn = build_graphs()
    payload = {}
    for name, func in CASES.items():
        fnx_value = func(fnx, gf)
        nx_value = func(nx, gn)
        payload[name] = {
            "fnx": normalize(fnx_value),
            "nx": normalize(nx_value),
            "equal_repr": normalize(fnx_value) == normalize(nx_value),
        }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return {
        "sha256": hashlib.sha256(encoded).hexdigest(),
        "payload": payload,
    }


def time_case(module_name, case_name, samples, loops):
    gf, gn = build_graphs()
    module = fnx if module_name == "fnx" else nx
    graph = gf if module_name == "fnx" else gn
    func = CASES[case_name]
    for _ in range(10):
        func(module, graph)
    timings = []
    for _ in range(samples):
        start = time.perf_counter()
        for _ in range(loops):
            func(module, graph)
        timings.append(time.perf_counter() - start)
    return {
        "module": module_name,
        "case": case_name,
        "samples": samples,
        "loops": loops,
        "median_sec": statistics.median(timings),
        "mean_sec": statistics.mean(timings),
        "min_sec": min(timings),
        "per_call_median_sec": statistics.median(timings) / loops,
        "samples_sec": timings,
    }


def profile_case(case_name, loops):
    gf, _ = build_graphs()
    func = CASES[case_name]
    profile = cProfile.Profile()
    profile.enable()
    for _ in range(loops):
        func(fnx, gf)
    profile.disable()
    stream = io.StringIO()
    stats = pstats.Stats(profile, stream=stream).sort_stats("cumulative")
    stats.print_stats(30)
    return stream.getvalue()


def run_baseline():
    loops = {
        "dijkstra_path_length": 300,
        "shortest_path_length": 300,
        "single_source_dijkstra": 40,
        "dijkstra_predecessor_and_distance": 40,
    }
    results = {
        "golden": collect_golden(),
        "timings": [],
        "profiles": {},
    }
    for case_name, case_loops in loops.items():
        results["timings"].append(time_case("fnx", case_name, 9, case_loops))
        results["timings"].append(time_case("nx", case_name, 9, case_loops))
        results["profiles"][case_name] = profile_case(case_name, min(80, case_loops))
    print(json.dumps(results, indent=2, sort_keys=True))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["baseline", "call"], default="baseline")
    parser.add_argument("--module", choices=["fnx", "nx"], default="fnx")
    parser.add_argument("--case", choices=sorted(CASES), default="dijkstra_path_length")
    parser.add_argument("--loops", type=int, default=300)
    args = parser.parse_args()
    if args.mode == "baseline":
        run_baseline()
        return
    gf, gn = build_graphs()
    module = fnx if args.module == "fnx" else nx
    graph = gf if args.module == "fnx" else gn
    func = CASES[args.case]
    for _ in range(args.loops):
        func(module, graph)


if __name__ == "__main__":
    main()
