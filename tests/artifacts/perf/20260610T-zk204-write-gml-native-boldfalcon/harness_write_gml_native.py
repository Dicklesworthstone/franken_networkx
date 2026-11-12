#!/usr/bin/env python3
"""Proof and timing harness for br-r37-c1-zk204."""

from __future__ import annotations

import argparse
import cProfile
import hashlib
import json
import os
import pstats
import random
import statistics
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

import networkx as nx

import franken_networkx as fnx
import franken_networkx._fnx as raw_fnx


def random_edges(nodes: int, edges: int, seed: int) -> list[tuple[int, int]]:
    rng = random.Random(seed)
    return [(rng.randrange(nodes), rng.randrange(nodes)) for _ in range(edges)]


def random_graphs(nodes: int, edges: int, seed: int) -> tuple[Any, nx.Graph]:
    edge_list = random_edges(nodes, edges, seed)
    return fnx.Graph(edge_list), nx.Graph(edge_list)


def temp_path(prefix: str) -> Path:
    handle = tempfile.NamedTemporaryFile(
        prefix=prefix,
        suffix=".gml",
        dir="/data/tmp",
        delete=False,
    )
    handle.close()
    return Path(handle.name)


def write_payload(kind: str, graph: Any, nx_graph: Any, path: Path) -> bytes:
    if kind == "fnx":
        fnx.write_gml(graph, path)
    elif kind == "nx":
        nx.write_gml(nx_graph, path)
    elif kind == "raw":
        raw_fnx.write_gml(graph, path)
    else:
        raise ValueError(kind)
    return path.read_bytes()


def graph_cases() -> list[tuple[str, Any, Any]]:
    cases: list[tuple[str, Any, Any]] = []
    for n in (0, 1, 2, 6, 30):
        cases.append((f"path-{n}", fnx.path_graph(n), nx.path_graph(n)))
    fg, ng = random_graphs(80, 240, 11)
    cases.append(("random-int-noattr", fg, ng))

    string_graph = fnx.Graph()
    string_graph.add_edge("a", "b")
    nx_string_graph = nx.Graph()
    nx_string_graph.add_edge("a", "b")
    cases.append(("string-label-fallback", string_graph, nx_string_graph))

    attr_graph = fnx.Graph()
    attr_graph.add_edge(1, 2, weight=3)
    nx_attr_graph = nx.Graph()
    nx_attr_graph.add_edge(1, 2, weight=3)
    cases.append(("edge-attr-fallback", attr_graph, nx_attr_graph))

    digraph = fnx.DiGraph()
    digraph.add_edges_from([(0, 1), (0, 2), (2, 1)])
    nx_digraph = nx.DiGraph()
    nx_digraph.add_edges_from([(0, 1), (0, 2), (2, 1)])
    cases.append(("digraph-fallback", digraph, nx_digraph))
    return cases


def proof() -> dict[str, Any]:
    root = Path(
        tempfile.mkdtemp(
            prefix=f"fnx_zk204_proof_{os.getpid()}_",
            dir="/data/tmp",
        )
    )
    failures: list[str] = []
    sha_rows: list[tuple[str, str]] = []
    for name, graph, nx_graph in graph_cases():
        fnx_path = root / f"{name}_fnx.gml"
        nx_path = root / f"{name}_nx.gml"
        fnx_payload = write_payload("fnx", graph, nx_graph, fnx_path)
        nx_payload = write_payload("nx", graph, nx_graph, nx_path)
        fnx_sha = hashlib.sha256(fnx_payload).hexdigest()
        nx_sha = hashlib.sha256(nx_payload).hexdigest()
        sha_rows.append((name, fnx_sha))
        if fnx_payload != nx_payload:
            failures.append(
                f"{name}: fnx sha {fnx_sha} != nx sha {nx_sha}; "
                f"lengths {len(fnx_payload)} != {len(nx_payload)}"
            )
    golden = hashlib.sha256(
        "\n".join(f"{name}:{sha}" for name, sha in sha_rows).encode("ascii")
    ).hexdigest()
    return {
        "cases": len(sha_rows),
        "failures": failures,
        "golden_sha256": golden,
        "mode": "proof",
        "ordering_tie_rng_fp": {
            "floating_point": "none; GML proof is byte-for-byte text output",
            "node_order": "cases construct nodes deterministically; proof compares exact bytes",
            "rng": "random-int-noattr uses deterministic seed=11",
            "tie_breaks": "no algorithmic tie-breaking; edge and node emission order are byte-checked",
        },
        "tmp": str(root),
    }


def time_impl(kind: str, nodes: int, edges: int, seed: int, repeats: int) -> dict[str, Any]:
    graph, nx_graph = random_graphs(nodes, edges, seed)
    path = temp_path(f"fnx_zk204_{kind}_{os.getpid()}_")
    times: list[float] = []
    digest = ""
    byte_len = 0
    for _ in range(repeats):
        start = time.perf_counter()
        payload = write_payload(kind, graph, nx_graph, path)
        elapsed = time.perf_counter() - start
        digest = hashlib.sha256(payload).hexdigest()
        byte_len = len(payload)
        times.append(elapsed)
    return {
        "bytes": byte_len,
        "digest": digest,
        "edges": graph.number_of_edges(),
        "impl": kind,
        "max_seconds": max(times),
        "mean_seconds": statistics.fmean(times),
        "median_seconds": statistics.median(times),
        "min_seconds": min(times),
        "mode": "time",
        "nodes": nodes,
        "repeats": repeats,
        "seed": seed,
    }


def profile(kind: str, nodes: int, edges: int, seed: int, repeats: int, output: Path) -> dict[str, Any]:
    graph, nx_graph = random_graphs(nodes, edges, seed)
    path = temp_path(f"fnx_zk204_profile_{kind}_{os.getpid()}_")

    def run() -> None:
        for _ in range(repeats):
            write_payload(kind, graph, nx_graph, path)

    profiler = cProfile.Profile()
    profiler.runcall(run)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as handle:
        pstats.Stats(profiler, stream=handle).strip_dirs().sort_stats("cumtime").print_stats(60)
    return {
        "impl": kind,
        "mode": "profile",
        "output": str(output),
        "repeats": repeats,
    }


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("proof")

    time_parser = sub.add_parser("time")
    time_parser.add_argument("--impl", choices=("fnx", "nx", "raw"), required=True)
    time_parser.add_argument("--nodes", type=int, default=3000)
    time_parser.add_argument("--edges", type=int, default=9000)
    time_parser.add_argument("--seed", type=int, default=1)
    time_parser.add_argument("--repeats", type=int, default=1)

    profile_parser = sub.add_parser("profile")
    profile_parser.add_argument("--impl", choices=("fnx", "nx", "raw"), required=True)
    profile_parser.add_argument("--nodes", type=int, default=3000)
    profile_parser.add_argument("--edges", type=int, default=9000)
    profile_parser.add_argument("--seed", type=int, default=1)
    profile_parser.add_argument("--repeats", type=int, default=3)
    profile_parser.add_argument("--output", type=Path, required=True)

    args = parser.parse_args(argv)
    if args.cmd == "proof":
        result = proof()
        print(json.dumps(result, sort_keys=True, indent=2))
        return 1 if result["failures"] else 0
    if args.cmd == "time":
        print(
            json.dumps(
                time_impl(args.impl, args.nodes, args.edges, args.seed, args.repeats),
                sort_keys=True,
            )
        )
        return 0
    if args.cmd == "profile":
        print(
            json.dumps(
                profile(args.impl, args.nodes, args.edges, args.seed, args.repeats, args.output),
                sort_keys=True,
            )
        )
        return 0
    raise AssertionError(args.cmd)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
