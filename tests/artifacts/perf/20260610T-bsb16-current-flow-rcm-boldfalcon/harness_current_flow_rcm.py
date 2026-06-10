#!/usr/bin/env python3
"""Benchmark/proof harness for br-r37-c1-bsb16 native RCM ordering."""

from __future__ import annotations

import argparse
import cProfile
import hashlib
import json
import pstats
import sys
import time
from pathlib import Path

import networkx as nx

import franken_networkx as fnx


CASES = {
    "watts_120": (120, 4, 0.12, 11),
    "watts_180": (180, 4, 0.10, 17),
    "watts_240": (240, 4, 0.08, 23),
}


def _nx_graph(case: str) -> nx.Graph:
    n, k, p, seed = CASES[case]
    return nx.watts_strogatz_graph(n, k, p, seed=seed)


def _fnx_graph(case: str) -> fnx.Graph:
    graph = fnx.Graph()
    graph.add_nodes_from(range(CASES[case][0]))
    graph.add_edges_from(_nx_graph(case).edges())
    return graph


def _normalize_mapping(mapping):
    return [(repr(key), float(value)) for key, value in mapping.items()]


def _normalize_edge_mapping(mapping):
    return [(repr(key), float(value)) for key, value in mapping.items()]


def _sha(payload) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _ordering(graph: fnx.Graph):
    return list(fnx._reverse_cuthill_mckee_ordering(graph))


def _native_start(graph: fnx.Graph):
    native = getattr(fnx._fnx, "current_flow_pseudo_peripheral_node_rust", None)
    if native is None:
        return None
    return native(graph)


def _native_start_ordering(graph: fnx.Graph):
    native_start = _native_start(graph)
    if native_start is None:
        return None
    return list(fnx._reverse_cuthill_mckee_ordering(graph, heuristic=lambda _graph: native_start))


def _call(graph: fnx.Graph, target: str):
    if target == "rcm":
        return _ordering(graph)
    if target == "native_rcm":
        native = _native_start_ordering(graph)
        if native is None:
            raise RuntimeError("native RCM start route is unavailable")
        return native
    if target == "node":
        return fnx.current_flow_betweenness_centrality(graph, normalized=True)
    if target == "edge":
        return fnx.edge_current_flow_betweenness_centrality(graph, normalized=True)
    raise ValueError(target)


def proof(args: argparse.Namespace) -> None:
    cases = ["watts_120", "watts_180", "watts_240"]
    payload = []
    native_available = hasattr(fnx._fnx, "current_flow_pseudo_peripheral_node_rust")
    for case in cases:
        graph = _fnx_graph(case)
        python_start = fnx._current_flow_pseudo_peripheral_node(graph)
        native_start = _native_start(graph)
        ordering = _ordering(graph)
        native_ordering = _native_start_ordering(graph)
        node = fnx.current_flow_betweenness_centrality(graph, normalized=True)
        edge = fnx.edge_current_flow_betweenness_centrality(graph, normalized=True)
        entry = {
            "case": case,
            "python_start": python_start,
            "native_start": native_start,
            "native_start_matches_python": native_start == python_start
            if native_start is not None
            else None,
            "ordering": ordering,
            "ordering_sha256": _sha(ordering),
            "native_available": native_available,
            "native_matches_python": native_ordering == ordering
            if native_ordering is not None
            else None,
            "node": _normalize_mapping(node),
            "node_sha256": _sha(_normalize_mapping(node)),
            "edge": _normalize_edge_mapping(edge),
            "edge_sha256": _sha(_normalize_edge_mapping(edge)),
        }
        payload.append(entry)
    result = {
        "payload_sha256": _sha(payload),
        "cases": payload,
    }
    Path(args.output).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")


def direct(args: argparse.Namespace) -> None:
    graph = _fnx_graph(args.case)
    _call(graph, args.target)
    times = []
    result = None
    for _ in range(args.repeat):
        start = time.perf_counter()
        result = _call(graph, args.target)
        times.append(time.perf_counter() - start)
    if isinstance(result, dict):
        normalized = (
            _normalize_edge_mapping(result) if args.target == "edge" else _normalize_mapping(result)
        )
    else:
        normalized = list(result)
    payload = {
        "case": args.case,
        "target": args.target,
        "repeat": args.repeat,
        "times": times,
        "min": min(times),
        "median": sorted(times)[len(times) // 2],
        "mean": sum(times) / len(times),
        "result_sha256": _sha(normalized),
    }
    Path(args.output).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def profile(args: argparse.Namespace) -> None:
    graph = _fnx_graph(args.case)
    _call(graph, args.target)
    profiler = cProfile.Profile()
    profiler.enable()
    for _ in range(args.repeat):
        _call(graph, args.target)
    profiler.disable()
    with Path(args.output).open("w") as handle:
        stats = pstats.Stats(profiler, stream=handle).sort_stats("cumulative")
        stats.print_stats(80)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="cmd", required=True)

    proof_parser = subparsers.add_parser("proof")
    proof_parser.add_argument("--output", required=True)
    proof_parser.set_defaults(func=proof)

    direct_parser = subparsers.add_parser("direct")
    direct_parser.add_argument("--target", choices=["rcm", "native_rcm", "node", "edge"], required=True)
    direct_parser.add_argument("--case", choices=sorted(CASES), default="watts_180")
    direct_parser.add_argument("--repeat", type=int, default=25)
    direct_parser.add_argument("--output", required=True)
    direct_parser.set_defaults(func=direct)

    profile_parser = subparsers.add_parser("profile")
    profile_parser.add_argument("--target", choices=["rcm", "native_rcm", "node", "edge"], required=True)
    profile_parser.add_argument("--case", choices=sorted(CASES), default="watts_180")
    profile_parser.add_argument("--repeat", type=int, default=25)
    profile_parser.add_argument("--output", required=True)
    profile_parser.set_defaults(func=profile)

    args = parser.parse_args(argv)
    args.func(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
