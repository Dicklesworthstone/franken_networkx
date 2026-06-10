#!/usr/bin/env python3
"""Profile/proof harness for br-r37-c1-1i2au current-flow/LU work."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import time
from pathlib import Path

import networkx as ref_nx

import franken_networkx as fnx


def stable_edges(graph_name: str, n: int) -> list[tuple[int, int]]:
    if graph_name == "cycle_chords":
        edges = {(i, (i + 1) % n) for i in range(n)}
        for i in range(n):
            edges.add(tuple(sorted((i, (i + 7) % n))))
            if i % 3 == 0:
                edges.add(tuple(sorted((i, (i + 13) % n))))
        return sorted(edges)
    if graph_name == "grid":
        side = int(math.sqrt(n))
        if side * side != n:
            raise SystemExit("grid graph requires n to be a perfect square")
        edges = []
        for row in range(side):
            for col in range(side):
                node = row * side + col
                if col + 1 < side:
                    edges.append((node, node + 1))
                if row + 1 < side:
                    edges.append((node, node + side))
        return edges
    if graph_name == "watts":
        graph = ref_nx.watts_strogatz_graph(n, 6, 0.19, seed=37)
        return sorted(tuple(sorted(edge)) for edge in graph.edges())
    raise SystemExit(f"unknown graph {graph_name!r}")


def build_graph(module, graph_name: str, n: int):
    graph = module.Graph()
    graph.add_nodes_from(range(n))
    graph.add_edges_from(stable_edges(graph_name, n))
    return graph


def canonical_value(value):
    if isinstance(value, dict):
        rows = []
        for key, inner in value.items():
            if isinstance(key, tuple):
                key_text = json.dumps(list(key), separators=(",", ":"))
            else:
                key_text = json.dumps(key, separators=(",", ":"))
            if isinstance(inner, dict):
                rows.append((key_text, canonical_value(inner)))
            else:
                rows.append((key_text, float(inner)))
        return sorted(rows, key=lambda item: item[0])
    return value


def digest(value) -> str:
    payload = json.dumps(canonical_value(value), separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(payload.encode()).hexdigest()


def result_for(module, func: str, graph_name: str, n: int, solver: str):
    graph = build_graph(module, graph_name, n)
    if func == "cfb":
        return module.current_flow_betweenness_centrality(
            graph, normalized=True, solver=solver
        )
    if func == "edge_cfb":
        return module.edge_current_flow_betweenness_centrality(
            graph, normalized=True, solver=solver
        )
    if func == "cfc":
        return module.current_flow_closeness_centrality(graph, solver=solver)
    raise SystemExit(f"unknown function {func!r}")


def flatten(value):
    flat = {}
    if isinstance(value, dict):
        for key, inner in value.items():
            if isinstance(key, tuple):
                key_text = json.dumps(list(key), separators=(",", ":"))
            else:
                key_text = json.dumps(key, separators=(",", ":"))
            if isinstance(inner, dict):
                for sub_key, sub_value in flatten(inner).items():
                    flat[f"{key_text}/{sub_key}"] = sub_value
            else:
                flat[key_text] = float(inner)
    return flat


def compare_outputs(fnx_value, nx_value):
    lhs = flatten(fnx_value)
    rhs = flatten(nx_value)
    keys_match = sorted(lhs) == sorted(rhs)
    max_abs = 0.0
    max_rel = 0.0
    worst_key = None
    for key in sorted(set(lhs) & set(rhs)):
        delta = abs(lhs[key] - rhs[key])
        denom = max(abs(rhs[key]), 1e-300)
        rel = delta / denom
        if delta > max_abs:
            max_abs = delta
            worst_key = key
        max_rel = max(max_rel, rel)
    return {
        "keys_match": keys_match,
        "max_abs": max_abs,
        "max_rel": max_rel,
        "worst_key": worst_key,
        "fnx_sha256": digest(fnx_value),
        "nx_sha256": digest(nx_value),
    }


def timed_call(module, func: str, graph_name: str, n: int, solver: str):
    start = time.perf_counter_ns()
    value = result_for(module, func, graph_name, n, solver)
    elapsed = (time.perf_counter_ns() - start) / 1e9
    return elapsed, value


def command_time(args):
    module = fnx if args.impl == "fnx" else ref_nx
    timings = []
    last = None
    for _ in range(args.repeats):
        elapsed, last = timed_call(module, args.func, args.graph, args.n, args.solver)
        timings.append(elapsed)
    result = {
        "mode": "time",
        "impl": args.impl,
        "func": args.func,
        "graph": args.graph,
        "n": args.n,
        "solver": args.solver,
        "repeats": args.repeats,
        "seconds": timings,
        "best_seconds": min(timings),
        "sha256": digest(last),
    }
    emit(result, args.out)


def command_proof(args):
    fnx_time, fnx_value = timed_call(fnx, args.func, args.graph, args.n, args.solver)
    nx_time, nx_value = timed_call(ref_nx, args.func, args.graph, args.n, args.solver)
    comparison = compare_outputs(fnx_value, nx_value)
    result = {
        "mode": "proof",
        "func": args.func,
        "graph": args.graph,
        "n": args.n,
        "solver": args.solver,
        "fnx_seconds": fnx_time,
        "nx_seconds": nx_time,
        "comparison": comparison,
        "ordering_tie_rng_fp": {
            "node_order": "nodes are inserted as range(n); RCM/relabel order follows each implementation's public algorithm",
            "tie_breaks": "proof compares final keyed outputs; no new tie-breaking lever is active in baseline",
            "rng": "graph generation is deterministic; watts uses seed=37",
            "floating_point": "baseline records numerical drift against genuine NetworkX for later equality envelope",
        },
    }
    emit(result, args.out)


def command_profile(args):
    import numpy as np

    graph = build_graph(fnx, args.graph, args.n)
    timings: dict[str, float] = {}

    start = time.perf_counter_ns()
    connected = fnx.is_connected(graph)
    timings["is_connected"] = (time.perf_counter_ns() - start) / 1e9
    if not connected:
        raise SystemExit("graph must be connected")

    start = time.perf_counter_ns()
    ordering = list(fnx._reverse_cuthill_mckee_ordering(graph))
    timings["reverse_cuthill_mckee"] = (time.perf_counter_ns() - start) / 1e9

    start = time.perf_counter_ns()
    relabeled = fnx.relabel_nodes(graph, dict(zip(ordering, range(args.n))), copy=True)
    timings["relabel_nodes"] = (time.perf_counter_ns() - start) / 1e9

    start = time.perf_counter_ns()
    laplacian = fnx.laplacian_matrix(
        relabeled, nodelist=range(args.n), weight=None
    ).asformat("csc")
    laplacian = laplacian.astype(float)
    timings["laplacian_csc"] = (time.perf_counter_ns() - start) / 1e9

    solver_classes = {
        "full": fnx._FullInverseLaplacian,
        "lu": fnx._SuperLUInverseLaplacian,
        "cg": fnx._CGInverseLaplacian,
    }
    start = time.perf_counter_ns()
    inverse = solver_classes[args.solver](laplacian, dtype=float)
    timings["solver_init"] = (time.perf_counter_ns() - start) / 1e9

    start = time.perf_counter_ns()
    row_count = 0
    checksum = 0.0
    width = inverse.w
    for u, v in sorted(tuple(sorted((u, v))) for u, v in relabeled.edges()):
        b = np.zeros(width, dtype=float)
        b[u % width] = 1.0
        b[v % width] = -1.0
        row = b @ inverse.get_rows(u, v)
        checksum += float(row.sum())
        row_count += 1
    timings["flow_rows_only"] = (time.perf_counter_ns() - start) / 1e9

    if args.func == "cfb":
        start = time.perf_counter_ns()
        _ = fnx.current_flow_betweenness_centrality(
            graph, normalized=True, solver=args.solver
        )
        timings["end_to_end_func"] = (time.perf_counter_ns() - start) / 1e9
    elif args.func == "edge_cfb":
        start = time.perf_counter_ns()
        _ = fnx.edge_current_flow_betweenness_centrality(
            graph, normalized=True, solver=args.solver
        )
        timings["end_to_end_func"] = (time.perf_counter_ns() - start) / 1e9
    elif args.func == "cfc":
        start = time.perf_counter_ns()
        _ = fnx.current_flow_closeness_centrality(graph, solver=args.solver)
        timings["end_to_end_func"] = (time.perf_counter_ns() - start) / 1e9

    result = {
        "mode": "profile",
        "func": args.func,
        "graph": args.graph,
        "n": args.n,
        "solver": args.solver,
        "edge_count": int(relabeled.number_of_edges()),
        "row_count": int(row_count),
        "inverse_width": int(width),
        "checksum": float(checksum),
        "timings": timings,
    }
    emit(result, args.out)


def emit(result, out_path):
    text = json.dumps(result, sort_keys=True, indent=2)
    print(text)
    if out_path is not None:
        Path(out_path).write_text(text + "\n", encoding="utf-8")


def parser():
    base = argparse.ArgumentParser()
    sub = base.add_subparsers(dest="command", required=True)

    def add_common(p):
        p.add_argument("--func", choices=("cfb", "edge_cfb", "cfc"), default="cfb")
        p.add_argument("--graph", choices=("cycle_chords", "grid", "watts"), default="watts")
        p.add_argument("--n", type=int, default=80)
        p.add_argument("--solver", choices=("full", "lu", "cg"), default="full")
        p.add_argument("--out")

    time_p = sub.add_parser("time")
    add_common(time_p)
    time_p.add_argument("--impl", choices=("fnx", "nx"), default="fnx")
    time_p.add_argument("--repeats", type=int, default=1)
    time_p.set_defaults(func_main=command_time)

    proof_p = sub.add_parser("proof")
    add_common(proof_p)
    proof_p.set_defaults(func_main=command_proof)

    profile_p = sub.add_parser("profile")
    add_common(profile_p)
    profile_p.set_defaults(func_main=command_profile)
    return base


def main():
    args = parser().parse_args()
    args.func_main(args)


if __name__ == "__main__":
    main()
