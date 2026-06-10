"""Profile and proof harness for br-r37-c1-3nzg8.

Targets the remaining spectral consumers that currently depend on NumPy/LAPACK.
The harness keeps the graph corpus deterministic and separates graph-to-matrix,
eigh/eigvalsh, and post-processing costs so the implementation lever stays
profile-backed.
"""

from __future__ import annotations

import argparse
import cProfile
import hashlib
import json
import pstats
import sys
import time
from io import StringIO

import networkx as nx
import numpy as np

import franken_networkx as fnx


genuine_subgraph_centrality = getattr(
    nx.subgraph_centrality, "orig_func", nx.subgraph_centrality
)
genuine_estrada_index = getattr(nx.estrada_index, "orig_func", nx.estrada_index)


def _to_fnx(graph):
    out = fnx.Graph()
    out.add_nodes_from(list(graph.nodes()))
    out.add_edges_from(list(graph.edges()))
    return out


def _corpus():
    graphs = [
        ("empty", nx.empty_graph(0)),
        ("single", nx.empty_graph(1)),
        ("path10", nx.path_graph(10)),
        ("cycle12", nx.cycle_graph(12)),
        ("complete8", nx.complete_graph(8)),
        ("star20", nx.star_graph(20)),
        ("wheel15", nx.wheel_graph(15)),
        ("karate", nx.karate_club_graph()),
        ("petersen", nx.petersen_graph()),
    ]
    for seed in range(4):
        graphs.append((f"gnp50_{seed}", nx.gnp_random_graph(50, 0.14, seed=seed)))
    for seed in range(3):
        graphs.append(
            (
                f"ws120_{seed}",
                nx.connected_watts_strogatz_graph(120, 6, 0.3, seed=seed),
            )
        )
    return graphs


def _stable_pairs(mapping):
    return sorted((repr(key), round(float(value), 9)) for key, value in mapping.items())


def golden():
    records = []
    max_rel_subgraph = 0.0
    max_rel_estrada = 0.0
    for name, graph in _corpus():
        fgraph = _to_fnx(graph)
        fnx_sub = fnx.subgraph_centrality(fgraph)
        nx_sub = genuine_subgraph_centrality(graph)
        for key, fnx_value in fnx_sub.items():
            nx_value = nx_sub[key]
            denom = abs(nx_value) if nx_value else 1.0
            max_rel_subgraph = max(
                max_rel_subgraph,
                abs(float(fnx_value) - float(nx_value)) / denom,
            )
        fnx_estrada = fnx.estrada_index(fgraph)
        nx_estrada = genuine_estrada_index(graph)
        denom = abs(nx_estrada) if nx_estrada else 1.0
        max_rel_estrada = max(
            max_rel_estrada,
            abs(float(fnx_estrada) - float(nx_estrada)) / denom,
        )
        records.append(
            (
                name,
                _stable_pairs(fnx_sub),
                round(float(fnx_estrada), 9),
            )
        )

    digest = hashlib.sha256(json.dumps(records, sort_keys=True).encode()).hexdigest()
    return {
        "max_rel_subgraph_vs_nx": max_rel_subgraph,
        "max_rel_estrada_vs_nx": max_rel_estrada,
        "rounded_corpus_sha256": digest,
        "within_1e_6": max_rel_subgraph < 1e-6 and max_rel_estrada < 1e-6,
    }


def _bench_graph(size: int):
    graph = nx.connected_watts_strogatz_graph(size, 6, 0.3, seed=7)
    return graph, _to_fnx(graph)


def _time_ms(func):
    start = time.perf_counter()
    value = func()
    return (time.perf_counter() - start) * 1000.0, value


def _warm_min(func, runs: int):
    for _ in range(2):
        func()
    best = float("inf")
    for _ in range(runs):
        elapsed, _ = _time_ms(func)
        best = min(best, elapsed)
    return best


def bench(impl: str, case: str, size: int, runs: int):
    graph, fgraph = _bench_graph(size)
    if impl == "fnx" and case == "subgraph":
        func = lambda: fnx.subgraph_centrality(fgraph)
    elif impl == "nx" and case == "subgraph":
        func = lambda: genuine_subgraph_centrality(graph)
    elif impl == "fnx" and case == "estrada":
        func = lambda: fnx.estrada_index(fgraph)
    elif impl == "nx" and case == "estrada":
        func = lambda: genuine_estrada_index(graph)
    else:
        raise ValueError(f"unknown bench case: {impl=} {case=}")
    return {
        "impl": impl,
        "case": case,
        "size": size,
        "runs": runs,
        "warm_min_ms": round(_warm_min(func, runs), 3),
    }


def phase_profile(size: int, runs: int):
    _, fgraph = _bench_graph(size)
    graph = fgraph
    timings = {"nodelist": [], "to_numpy_array": [], "binarize": [], "eigh": [], "post": []}
    digest_records = []
    for _ in range(runs):
        t0 = time.perf_counter()
        nodelist = list(graph.nodes())
        t1 = time.perf_counter()
        matrix = fnx.to_numpy_array(graph, nodelist=nodelist, weight=None)
        t2 = time.perf_counter()
        matrix[np.nonzero(matrix)] = 1
        t3 = time.perf_counter()
        eigenvalues, eigenvectors = np.linalg.eigh(matrix)
        t4 = time.perf_counter()
        squared = np.array(eigenvectors) ** 2
        centralities = squared @ np.exp(eigenvalues)
        result = {nodelist[i]: float(centralities[i]) for i in range(len(nodelist))}
        t5 = time.perf_counter()
        timings["nodelist"].append((t1 - t0) * 1000.0)
        timings["to_numpy_array"].append((t2 - t1) * 1000.0)
        timings["binarize"].append((t3 - t2) * 1000.0)
        timings["eigh"].append((t4 - t3) * 1000.0)
        timings["post"].append((t5 - t4) * 1000.0)
        digest_records.append(_stable_pairs(result)[:8])

    return {
        "size": size,
        "runs": runs,
        "phase_min_ms": {key: round(min(values), 3) for key, values in timings.items()},
        "digest_sha256": hashlib.sha256(
            json.dumps(digest_records, sort_keys=True).encode()
        ).hexdigest(),
    }


def cprofile_text(size: int, limit: int):
    _, fgraph = _bench_graph(size)
    profiler = cProfile.Profile()
    profiler.enable()
    fnx.subgraph_centrality(fgraph)
    profiler.disable()
    out = StringIO()
    pstats.Stats(profiler, stream=out).sort_stats("cumtime").print_stats(limit)
    return out.getvalue()


def main(argv):
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="cmd", required=True)

    subparsers.add_parser("golden")

    bench_parser = subparsers.add_parser("bench")
    bench_parser.add_argument("--impl", choices=("fnx", "nx"), required=True)
    bench_parser.add_argument("--case", choices=("subgraph", "estrada"), required=True)
    bench_parser.add_argument("--size", type=int, default=260)
    bench_parser.add_argument("--runs", type=int, default=9)

    phase_parser = subparsers.add_parser("phase-profile")
    phase_parser.add_argument("--size", type=int, default=260)
    phase_parser.add_argument("--runs", type=int, default=7)

    profile_parser = subparsers.add_parser("cprofile")
    profile_parser.add_argument("--size", type=int, default=260)
    profile_parser.add_argument("--limit", type=int, default=24)

    args = parser.parse_args(argv)
    if args.cmd == "golden":
        print(json.dumps(golden(), indent=2, sort_keys=True))
    elif args.cmd == "bench":
        print(json.dumps(bench(args.impl, args.case, args.size, args.runs), sort_keys=True))
    elif args.cmd == "phase-profile":
        print(json.dumps(phase_profile(args.size, args.runs), indent=2, sort_keys=True))
    elif args.cmd == "cprofile":
        print(cprofile_text(args.size, args.limit), end="")


if __name__ == "__main__":
    main(sys.argv[1:])
