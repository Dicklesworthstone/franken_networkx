#!/usr/bin/env python3
"""Benchmark/proof harness for br-r37-c1-c1gz0.

The before mode forces the pre-change global path by making the new
connectivity predicate return connected, which sends disconnected delegated
shapes through the old NetworkX conversion route.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import random
import statistics
import time
from pathlib import Path
from typing import Any, Callable, Iterator

import networkx as nx
from networkx.algorithms.flow import edmonds_karp

import franken_networkx as fnx


def make_edges(nodes: int, edges: int, *, seed: int) -> list[tuple[int, int]]:
    rng = random.Random(seed)
    out: list[tuple[int, int]] = []
    # Keep all random edges in the first component; nodes >= nodes * 2 // 3
    # remain isolated, so global connectivity must return 0.
    span = nodes * 2 // 3
    while len(out) < edges:
        u = rng.randrange(span)
        v = rng.randrange(span)
        if u != v:
            out.append((u, v))
    return out


def make_graphs(
    mod: Any,
    *,
    directed: bool,
    multi: bool,
    selfloop: bool,
    nodes: int,
    edges: int,
    seed: int,
) -> Any:
    cls = (
        (mod.MultiDiGraph if multi else mod.DiGraph)
        if directed
        else (mod.MultiGraph if multi else mod.Graph)
    )
    graph = cls()
    graph.add_nodes_from(range(nodes))
    graph.add_edges_from(make_edges(nodes, edges, seed=seed))
    if selfloop:
        graph.add_edge(0, 0)
    return graph


@contextlib.contextmanager
def force_old_global_path() -> Iterator[None]:
    old_connected = fnx.is_connected
    old_weak = fnx.is_weakly_connected
    fnx.is_connected = lambda graph: True
    fnx.is_weakly_connected = lambda graph: True
    try:
        yield
    finally:
        fnx.is_connected = old_connected
        fnx.is_weakly_connected = old_weak


def call_case(name: str, graph: Any) -> int:
    if name == "node_selfloop":
        return fnx.node_connectivity(graph)
    if name == "node_flow":
        return fnx.node_connectivity(graph, flow_func=edmonds_karp)
    if name == "edge_cutoff":
        return fnx.edge_connectivity(graph, cutoff=2)
    raise ValueError(f"unknown case: {name}")


def call_nx_case(name: str, graph: Any) -> int:
    if name == "node_selfloop":
        return nx.node_connectivity(graph)
    if name == "node_flow":
        return nx.node_connectivity(graph, flow_func=edmonds_karp)
    if name == "edge_cutoff":
        return nx.edge_connectivity(graph, cutoff=2)
    raise ValueError(f"unknown case: {name}")


def graph_for_case(mod: Any, name: str, *, nodes: int, edges: int) -> Any:
    if name == "node_selfloop":
        return make_graphs(
            mod,
            directed=False,
            multi=False,
            selfloop=True,
            nodes=nodes,
            edges=edges,
            seed=17,
        )
    if name == "node_flow":
        return make_graphs(
            mod,
            directed=False,
            multi=False,
            selfloop=False,
            nodes=nodes,
            edges=edges,
            seed=23,
        )
    if name == "edge_cutoff":
        return make_graphs(
            mod,
            directed=True,
            multi=False,
            selfloop=False,
            nodes=nodes,
            edges=edges,
            seed=31,
        )
    raise ValueError(f"unknown case: {name}")


def bench(
    *,
    mode: str,
    case: str,
    nodes: int,
    edges: int,
    loops: int,
    repeat: int,
) -> dict[str, Any]:
    graph = graph_for_case(fnx, case, nodes=nodes, edges=edges)
    timings: list[float] = []
    values: list[int] = []
    context: Callable[[], contextlib.AbstractContextManager[None]]
    context = force_old_global_path if mode == "before" else contextlib.nullcontext
    with context():
        for _ in range(repeat):
            start = time.perf_counter()
            result = None
            for _ in range(loops):
                result = call_case(case, graph)
            elapsed = time.perf_counter() - start
            timings.append(elapsed / loops)
            values.append(int(result))
    return {
        "mode": mode,
        "case": case,
        "nodes": nodes,
        "edges": edges,
        "loops": loops,
        "repeat": repeat,
        "values": values,
        "best_seconds_per_call": min(timings),
        "median_seconds_per_call": statistics.median(timings),
        "mean_seconds_per_call": statistics.fmean(timings),
    }


def proof(*, nodes: int, edges: int) -> dict[str, Any]:
    cases: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    for name in ("node_selfloop", "node_flow", "edge_cutoff"):
        fnx_graph = graph_for_case(fnx, name, nodes=nodes, edges=edges)
        nx_graph = graph_for_case(nx, name, nodes=nodes, edges=edges)
        after = call_case(name, fnx_graph)
        before_ctx = force_old_global_path()
        with before_ctx:
            before = call_case(name, fnx_graph)
        expected = call_nx_case(name, nx_graph)
        row = {
            "case": name,
            "before": before,
            "after": after,
            "networkx": expected,
        }
        cases.append(row)
        if before != expected or after != expected:
            failures.append(row)

    encoded = json.dumps(cases, sort_keys=True, separators=(",", ":")).encode()
    return {
        "cases": cases,
        "failures": failures,
        "golden_sha256": hashlib.sha256(encoded).hexdigest(),
        "proof_note": "scalar integer outputs; no ordering, FP, or tie-break surface; RNG seeds fixed",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    bench_parser = sub.add_parser("bench")
    bench_parser.add_argument("--mode", choices=["before", "after"], required=True)
    bench_parser.add_argument(
        "--case",
        choices=["node_selfloop", "node_flow", "edge_cutoff"],
        default="node_selfloop",
    )
    bench_parser.add_argument("--nodes", type=int, default=1500)
    bench_parser.add_argument("--edges", type=int, default=1200)
    bench_parser.add_argument("--loops", type=int, default=30)
    bench_parser.add_argument("--repeat", type=int, default=9)
    bench_parser.add_argument("--output", type=Path)

    proof_parser = sub.add_parser("proof")
    proof_parser.add_argument("--nodes", type=int, default=1500)
    proof_parser.add_argument("--edges", type=int, default=1200)
    proof_parser.add_argument("--output", type=Path)

    args = parser.parse_args()
    if args.command == "bench":
        result = bench(
            mode=args.mode,
            case=args.case,
            nodes=args.nodes,
            edges=args.edges,
            loops=args.loops,
            repeat=args.repeat,
        )
    else:
        result = proof(nodes=args.nodes, edges=args.edges)
    text = json.dumps(result, indent=2, sort_keys=True)
    print(text)
    if args.output is not None:
        args.output.write_text(text + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
