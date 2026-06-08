#!/usr/bin/env python3
"""Proof and benchmark harness for nested subgraph edge-view residuals."""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import time
from pathlib import Path

import franken_networkx as fnx
import networkx as nx


def _add_edges(mod, graph, *, multi: bool, directed: bool, n: int) -> None:
    for i in range(n):
        graph.add_node(i, color=f"c{i % 5}")
    for i in range(n):
        u = i
        v1 = (i * 17 + 11) % n
        v2 = (i + 1) % n
        if multi:
            graph.add_edge(u, v1, key=f"k{i}:a", weight=(i % 7) + 1, tag=f"a{i % 3}")
            graph.add_edge(u, v1, key=f"k{i}:b", weight=(i % 11) + 2, tag=f"b{i % 5}")
            graph.add_edge(u, v2, key=f"k{i}:c", weight=(i % 13) + 3)
        else:
            graph.add_edge(u, v1, weight=(i % 7) + 1, tag=f"a{i % 3}")
            graph.add_edge(u, v2, weight=(i % 11) + 2)
        if directed:
            back = (i * 19 + 7) % n
            if multi:
                graph.add_edge(back, u, key=f"r{i}", weight=(i % 5) + 4)
            else:
                graph.add_edge(back, u, weight=(i % 5) + 4)
    if multi:
        graph.add_edge(0, 0, key="loop", weight=99, loop=True)
    else:
        graph.add_edge(0, 0, weight=99, loop=True)


def build_graph(mod, case: str, n: int):
    if case.startswith("graph"):
        graph = mod.Graph()
        _add_edges(mod, graph, multi=False, directed=False, n=n)
        return graph
    if case.startswith("digraph"):
        graph = mod.DiGraph()
        _add_edges(mod, graph, multi=False, directed=True, n=n)
        return graph
    if case.startswith("multigraph"):
        graph = mod.MultiGraph()
        _add_edges(mod, graph, multi=True, directed=False, n=n)
        return graph
    if case.startswith("multidigraph"):
        graph = mod.MultiDiGraph()
        _add_edges(mod, graph, multi=True, directed=True, n=n)
        return graph
    raise ValueError(f"unknown case {case!r}")


def nested_view(graph, n: int):
    keep_outer = {i for i in range(n) if i % 5 != 0}
    keep_inner = {i for i in range(n) if i % 7 != 0}
    return graph.subgraph(keep_outer).subgraph(keep_inner)


def _norm_value(value):
    if isinstance(value, dict):
        return {repr(k): _norm_value(v) for k, v in sorted(value.items(), key=lambda item: repr(item[0]))}
    if isinstance(value, tuple):
        return [_norm_value(v) for v in value]
    if isinstance(value, list):
        return [_norm_value(v) for v in value]
    return repr(value)


def snapshot(mod, case: str, n: int):
    graph = build_graph(mod, case, n)
    view = nested_view(graph, n)
    multi = graph.is_multigraph()
    edge_view = view.edges
    record = {
        "case": case,
        "edge_view_type": type(edge_view).__name__,
        "edge_view_repr_prefix": repr(edge_view)[:120],
        "nodes": [repr(node) for node in view],
    }
    if multi:
        record["iter"] = _norm_value(list(edge_view))
        record["call"] = _norm_value(list(edge_view()))
        record["keys_data"] = _norm_value(list(edge_view(keys=True, data=True)))
        record["keys_weight"] = _norm_value(list(edge_view(keys=True, data="weight", default=-1)))
        record["keys_none"] = _norm_value(list(edge_view(keys=True, data=None, default="D")))
    else:
        record["iter"] = _norm_value(list(edge_view))
        record["call"] = _norm_value(list(edge_view()))
        record["data"] = _norm_value(list(edge_view(data=True)))
        record["weight"] = _norm_value(list(edge_view(data="weight", default=-1)))
        record["none"] = _norm_value(list(edge_view(data=None, default="D")))
    return record


def proof(out: Path) -> None:
    cases = ("graph_nested", "digraph_nested", "multigraph_nested", "multidigraph_nested")
    rows = []
    for case in cases:
        fnx_snapshot = snapshot(fnx, case, 48)
        nx_snapshot = snapshot(nx, case, 48)
        if fnx_snapshot != nx_snapshot:
            raise AssertionError(
                json.dumps(
                    {"case": case, "fnx": fnx_snapshot, "nx": nx_snapshot},
                    indent=2,
                    sort_keys=True,
                )
            )
        rows.append(fnx_snapshot)
    payload = {
        "cases": rows,
        "sha256": hashlib.sha256(
            json.dumps(rows, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest(),
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(payload["sha256"])


def bench_one(mod, case: str, n: int, loops: int):
    graph = build_graph(mod, case, n)
    view = nested_view(graph, n)
    total = 0
    t0 = time.perf_counter()
    for _ in range(loops):
        if graph.is_multigraph():
            total += len(list(view.edges(keys=True, data=True)))
        else:
            total += len(list(view.edges(data=True)))
    elapsed = time.perf_counter() - t0
    print(json.dumps({"case": case, "impl": mod.__name__, "loops": loops, "n": n, "edges_seen": total, "seconds": elapsed}))


def sample(mod, case: str, n: int, loops: int, repeats: int, out: Path) -> None:
    samples = []
    for _ in range(repeats):
        graph = build_graph(mod, case, n)
        view = nested_view(graph, n)
        t0 = time.perf_counter()
        total = 0
        for _ in range(loops):
            if graph.is_multigraph():
                total += len(list(view.edges(keys=True, data=True)))
            else:
                total += len(list(view.edges(data=True)))
        samples.append(time.perf_counter() - t0)
    payload = {
        "case": case,
        "impl": mod.__name__,
        "loops": loops,
        "n": n,
        "repeats": repeats,
        "edges_seen": total,
        "samples": samples,
        "mean": statistics.mean(samples),
        "median": statistics.median(samples),
        "min": min(samples),
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(json.dumps(payload, sort_keys=True))


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    proof_p = sub.add_parser("proof")
    proof_p.add_argument("--out", type=Path, required=True)
    bench_p = sub.add_parser("bench")
    bench_p.add_argument("--impl", choices=("fnx", "nx"), required=True)
    bench_p.add_argument("--case", required=True)
    bench_p.add_argument("--n", type=int, default=2500)
    bench_p.add_argument("--loops", type=int, default=20)
    sample_p = sub.add_parser("sample")
    sample_p.add_argument("--impl", choices=("fnx", "nx"), required=True)
    sample_p.add_argument("--case", required=True)
    sample_p.add_argument("--n", type=int, default=2500)
    sample_p.add_argument("--loops", type=int, default=20)
    sample_p.add_argument("--repeats", type=int, default=7)
    sample_p.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.cmd == "proof":
        proof(args.out)
    elif args.cmd == "bench":
        bench_one(fnx if args.impl == "fnx" else nx, args.case, args.n, args.loops)
    else:
        sample(fnx if args.impl == "fnx" else nx, args.case, args.n, args.loops, args.repeats, args.out)


if __name__ == "__main__":
    main()
