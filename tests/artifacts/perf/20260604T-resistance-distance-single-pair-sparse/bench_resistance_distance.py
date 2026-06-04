#!/usr/bin/env python3
from __future__ import annotations

import argparse
import cProfile
import hashlib
import json
import math
import pstats
import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "python"))

import networkx as nx
import numpy as np

import franken_networkx as fnx


def _copy_to_fnx(graph):
    copied = fnx.MultiGraph() if graph.is_multigraph() else fnx.Graph()
    copied.add_nodes_from(graph.nodes(data=True))
    if graph.is_multigraph():
        copied.add_edges_from(graph.edges(keys=True, data=True))
    else:
        copied.add_edges_from(graph.edges(data=True))
    return copied


def _sparse_graph(n: int, *, weighted: bool, multigraph: bool, seed: int):
    graph = nx.connected_watts_strogatz_graph(n, 6, 0.25, seed=seed)
    rng = random.Random(seed * 1009 + n)  # nosec B311 - deterministic fixture RNG
    if weighted:
        for u, v in graph.edges():
            graph[u][v]["weight"] = round(rng.uniform(0.35, 5.0), 6)
    if multigraph:
        multi = nx.MultiGraph()
        multi.add_nodes_from(graph.nodes(data=True))
        multi.add_edges_from(graph.edges(data=True))
        for u, v in list(graph.edges())[: max(1, n // 20)]:
            attrs = dict(graph[u][v])
            if weighted:
                attrs["weight"] = round(attrs["weight"] + rng.uniform(0.1, 0.7), 6)
            multi.add_edge(u, v, **attrs)
        graph = multi
    return graph, _copy_to_fnx(graph)


def _case(case: str):
    if case == "unweighted_sparse_pair":
        graph_nx, graph_fnx = _sparse_graph(
            420, weighted=False, multigraph=False, seed=17
        )
        return graph_nx, graph_fnx, 0, 419, None, True
    if case == "weighted_sparse_pair":
        graph_nx, graph_fnx = _sparse_graph(
            320, weighted=True, multigraph=False, seed=23
        )
        return graph_nx, graph_fnx, 0, 319, "weight", True
    if case == "weighted_multigraph_pair":
        graph_nx, graph_fnx = _sparse_graph(
            220, weighted=True, multigraph=True, seed=29
        )
        return graph_nx, graph_fnx, 0, 219, "weight", True
    raise ValueError(f"unknown case: {case}")


def _exact_dense_pair(graph, node_a, node_b, weight=None, invert_weight=True):
    if graph.is_directed():
        raise fnx.NetworkXNotImplemented("not implemented for directed type")
    nodelist = list(graph.nodes())
    if not nodelist:
        raise fnx.NetworkXError("Graph G must contain at least one node.")
    if node_a is not None and node_a not in graph:
        raise fnx.NetworkXError("Node A is not in graph G.")
    if node_b is not None and node_b not in graph:
        raise fnx.NetworkXError("Node B is not in graph G.")
    if not fnx.is_connected(graph):
        raise fnx.NetworkXError("Graph G must be strongly connected.")

    working = graph
    if invert_weight and weight is not None:
        working = graph.copy()
        if working.is_multigraph():
            for u, v, k, data in working.edges(keys=True, data=True):
                working[u][v][k][weight] = 1 / data[weight]
        else:
            for u, v, data in working.edges(data=True):
                working[u][v][weight] = 1 / data[weight]

    laplacian = fnx.laplacian_matrix(working, nodelist=nodelist, weight=weight).toarray()
    inverse = np.linalg.pinv(laplacian, hermitian=True)
    index = {node: i for i, node in enumerate(nodelist)}
    i, j = index[node_a], index[node_b]
    return float(inverse[i, i] + inverse[j, j] - inverse[i, j] - inverse[j, i])


def _run_one(impl: str, case: str):
    graph_nx, graph_fnx, node_a, node_b, weight, invert_weight = _case(case)
    if impl == "fnx":
        return fnx.resistance_distance(
            graph_fnx,
            node_a,
            node_b,
            weight=weight,
            invert_weight=invert_weight,
        )
    if impl == "nx":
        return nx.resistance_distance(
            graph_nx,
            node_a,
            node_b,
            weight=weight,
            invert_weight=invert_weight,
        )
    if impl == "dense_exact":
        return _exact_dense_pair(
            graph_fnx,
            node_a,
            node_b,
            weight=weight,
            invert_weight=invert_weight,
        )
    raise ValueError(f"unknown impl: {impl}")


def _timed(impl: str, case: str, repeats: int):
    values = []
    elapsed = []
    for _ in range(repeats):
        start = time.perf_counter()
        values.append(_run_one(impl, case))
        elapsed.append(time.perf_counter() - start)
    return {
        "case": case,
        "impl": impl,
        "repeats": repeats,
        "mean_s": sum(elapsed) / len(elapsed),
        "min_s": min(elapsed),
        "max_s": max(elapsed),
        "value": values[-1],
        "rounded_value": round(values[-1], 10),
    }


def _digest(records):
    payload = []
    for record in records:
        value = record["value"]
        payload.append(
            {
                "case": record["case"],
                "impl": record["impl"],
                "value": "nan" if math.isnan(value) else round(value, 8),
            }
        )
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest(), payload


def cmd_bench(args):
    cases = (
        ["unweighted_sparse_pair", "weighted_sparse_pair", "weighted_multigraph_pair"]
        if args.case == "all"
        else [args.case]
    )
    impls = ["fnx", "nx", "dense_exact"] if args.impl == "all" else [args.impl]
    for case in cases:
        for impl in impls:
            print(json.dumps(_timed(impl, case, args.repeats), sort_keys=True), flush=True)


def cmd_profile(args):
    profile = cProfile.Profile()
    profile.enable()
    result = None
    for _ in range(args.repeats):
        result = _run_one(args.impl, args.case)
    profile.disable()
    with Path(args.output).open("w", encoding="utf-8") as handle:
        stats = pstats.Stats(profile, stream=handle)
        stats.strip_dirs().sort_stats("cumtime").print_stats(args.limit)
    print(
        json.dumps(
            {
                "case": args.case,
                "impl": args.impl,
                "repeats": args.repeats,
                "value": result,
                "profile": args.output,
            },
            sort_keys=True,
        )
    )


def cmd_golden(args):
    cases = [
        "unweighted_sparse_pair",
        "weighted_sparse_pair",
        "weighted_multigraph_pair",
    ]
    records = []
    for case in cases:
        for impl in ("fnx", "dense_exact", "nx"):
            record = _timed(impl, case, 1)
            records.append(record)
    digest, payload = _digest(records)
    result = {"digest": digest, "records": payload}
    print(json.dumps(result, indent=2, sort_keys=True))


def main():
    parser = argparse.ArgumentParser()
    subcommands = parser.add_subparsers(dest="command", required=True)

    bench = subcommands.add_parser("bench")
    bench.add_argument("--case", default="all")
    bench.add_argument("--impl", default="fnx")
    bench.add_argument("--repeats", type=int, default=5)
    bench.set_defaults(func=cmd_bench)

    profile = subcommands.add_parser("profile")
    profile.add_argument("--case", default="unweighted_sparse_pair")
    profile.add_argument("--impl", default="fnx")
    profile.add_argument("--repeats", type=int, default=3)
    profile.add_argument("--limit", type=int, default=60)
    profile.add_argument("--output", required=True)
    profile.set_defaults(func=cmd_profile)

    golden = subcommands.add_parser("golden")
    golden.set_defaults(func=cmd_golden)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
