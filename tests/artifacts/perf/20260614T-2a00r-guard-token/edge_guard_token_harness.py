#!/usr/bin/env python3
"""Baseline/proof harness for br-r37-c1-2a00r guard-token work."""

from __future__ import annotations

import argparse
import cProfile
import hashlib
import io
import json
import pstats
import statistics
import time
from pathlib import Path
from typing import Any

import networkx as nx

import franken_networkx as fnx


def make_pair(nodes: int, stride: int, extra_stride: int) -> tuple[Any, Any]:
    fg = fnx.DiGraph()
    ng = nx.DiGraph()
    for graph in (fg, ng):
        graph.add_nodes_from(range(nodes))
        for u in range(nodes):
            graph.add_edge(u, (u + 1) % nodes, w=u % 7)
            graph.add_edge(u, (u + stride) % nodes, w=(u * 3) % 11)
            if u % 2 == 0:
                graph.add_edge(u, (u + extra_stride) % nodes, w=(u * 5) % 13)
    return fg, ng


def _edge_payload(edges: Any) -> list[Any]:
    payload = []
    for edge in edges:
        if len(edge) == 2:
            u, v = edge
            payload.append([repr(u), repr(v)])
        else:
            u, v, data = edge
            if isinstance(data, dict):
                data = sorted((repr(k), repr(v)) for k, v in data.items())
            payload.append([repr(u), repr(v), data])
    return payload


def _digest(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _mutation_checks(graph: Any) -> dict[str, str]:
    checks: dict[str, str] = {}

    it = iter(graph.edges)
    next(it)
    graph.add_edge("__new_u__", "__new_v__")
    try:
        next(it)
    except RuntimeError as exc:
        checks["edge_add_after_iter"] = str(exc)
    else:
        checks["edge_add_after_iter"] = "NO_ERROR"
    graph.remove_edge("__new_u__", "__new_v__")
    graph.remove_node("__new_u__")
    graph.remove_node("__new_v__")

    it = iter(graph.edges(data=True))
    next(it)
    graph.add_node("__new_node__")
    try:
        next(it)
    except RuntimeError as exc:
        checks["node_add_after_data_iter"] = str(exc)
    else:
        checks["node_add_after_data_iter"] = "NO_ERROR"
    graph.remove_node("__new_node__")

    view = graph.edges()
    before = len(list(view))
    graph.add_edge(0, "__late__")
    after = len(list(view))
    checks["bare_live_view_delta"] = f"{before}->{after}"
    graph.remove_edge(0, "__late__")
    graph.remove_node("__late__")

    return checks


def semantics(nodes: int, stride: int, extra_stride: int) -> dict[str, Any]:
    fg, ng = make_pair(nodes, stride, extra_stride)
    cases = {
        "edges": (list(fg.edges), list(ng.edges)),
        "edges_call": (list(fg.edges()), list(ng.edges())),
        "edges_data_true": (list(fg.edges(data=True)), list(ng.edges(data=True))),
        "edges_data_key": (
            list(fg.edges(data="w", default=-1)),
            list(ng.edges(data="w", default=-1)),
        ),
    }
    payload: dict[str, Any] = {
        "case": {"nodes": nodes, "stride": stride, "extra_stride": extra_stride},
        "edge_count": fg.number_of_edges(),
        "cases": {},
        "mutation_checks": _mutation_checks(fg),
    }
    for name, (fnx_edges, nx_edges) in cases.items():
        fnx_payload = _edge_payload(fnx_edges)
        nx_payload = _edge_payload(nx_edges)
        payload["cases"][name] = {
            "fnx_sha256": _digest(fnx_payload),
            "nx_sha256": _digest(nx_payload),
            "match": fnx_payload == nx_payload,
            "sample": fnx_payload[:8],
        }
    return payload


def golden(nodes: int, stride: int, extra_stride: int, output: Path | None) -> dict[str, Any]:
    payload = semantics(nodes, stride, extra_stride)
    result = {"sha256": _digest(payload), "payload": payload}
    if output is not None:
        output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    return result


def drain(graph: Any, mode: str) -> int:
    if mode == "edges":
        return len(list(graph.edges))
    if mode == "edges_call":
        return len(list(graph.edges()))
    if mode == "data_true":
        return len(list(graph.edges(data=True)))
    if mode == "data_key":
        return len(list(graph.edges(data="w", default=-1)))
    raise ValueError(mode)


def bench_once(nodes: int, stride: int, extra_stride: int, library: str, mode: str, loops: int) -> float:
    fg, ng = make_pair(nodes, stride, extra_stride)
    graph = fg if library == "fnx" else ng
    drain(graph, mode)
    start = time.perf_counter()
    total = 0
    for _ in range(loops):
        total += drain(graph, mode)
    elapsed = time.perf_counter() - start
    expected = graph.number_of_edges() * loops
    if total != expected:
        raise SystemExit(f"drain mismatch: {total} != {expected}")
    return elapsed


def bench(
    nodes: int,
    stride: int,
    extra_stride: int,
    library: str,
    mode: str,
    loops: int,
    samples: int,
    output: Path | None,
) -> dict[str, Any]:
    runs = [bench_once(nodes, stride, extra_stride, library, mode, loops) for _ in range(samples)]
    per_loop = [elapsed / loops for elapsed in runs]
    result = {
        "case": {
            "nodes": nodes,
            "stride": stride,
            "extra_stride": extra_stride,
            "edge_count": make_pair(nodes, stride, extra_stride)[0].number_of_edges(),
            "library": library,
            "mode": mode,
        },
        "loops": loops,
        "samples": samples,
        "seconds": runs,
        "per_loop_seconds": per_loop,
        "median_per_loop_seconds": statistics.median(per_loop),
        "mean_per_loop_seconds": statistics.fmean(per_loop),
    }
    if output is not None:
        output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    return result


def profile(
    nodes: int,
    stride: int,
    extra_stride: int,
    library: str,
    mode: str,
    loops: int,
    output: Path,
) -> dict[str, Any]:
    profiler = cProfile.Profile()
    profiler.enable()
    elapsed = bench_once(nodes, stride, extra_stride, library, mode, loops)
    profiler.disable()
    summary = io.StringIO()
    stats = pstats.Stats(profiler, stream=summary).strip_dirs().sort_stats("cumtime")
    stats.print_stats(45)
    output.write_text(summary.getvalue())
    return {
        "case": {
            "nodes": nodes,
            "stride": stride,
            "extra_stride": extra_stride,
            "library": library,
            "mode": mode,
        },
        "loops": loops,
        "elapsed_seconds": elapsed,
        "profile": str(output),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--nodes", type=int, default=2000)
    parser.add_argument("--stride", type=int, default=17)
    parser.add_argument("--extra-stride", type=int, default=47)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_golden = sub.add_parser("golden")
    p_golden.add_argument("--output", type=Path)

    p_bench = sub.add_parser("bench")
    p_bench.add_argument("--library", choices=("fnx", "nx"), default="fnx")
    p_bench.add_argument("--mode", choices=("edges", "edges_call", "data_true", "data_key"), default="edges")
    p_bench.add_argument("--loops", type=int, default=80)
    p_bench.add_argument("--samples", type=int, default=9)
    p_bench.add_argument("--output", type=Path)

    p_profile = sub.add_parser("profile")
    p_profile.add_argument("--library", choices=("fnx", "nx"), default="fnx")
    p_profile.add_argument("--mode", choices=("edges", "edges_call", "data_true", "data_key"), default="edges")
    p_profile.add_argument("--loops", type=int, default=80)
    p_profile.add_argument("--output", type=Path, required=True)

    args = parser.parse_args()
    if args.cmd == "golden":
        result = golden(args.nodes, args.stride, args.extra_stride, args.output)
    elif args.cmd == "bench":
        result = bench(
            args.nodes,
            args.stride,
            args.extra_stride,
            args.library,
            args.mode,
            args.loops,
            args.samples,
            args.output,
        )
    else:
        result = profile(
            args.nodes,
            args.stride,
            args.extra_stride,
            args.library,
            args.mode,
            args.loops,
            args.output,
        )
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
