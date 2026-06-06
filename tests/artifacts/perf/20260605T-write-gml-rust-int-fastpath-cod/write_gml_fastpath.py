#!/usr/bin/env python3
"""Benchmark/proof harness for br-r37-c1-43n6s."""

from __future__ import annotations

import argparse
import cProfile
import hashlib
import json
import os
import pstats
import random
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

import networkx as nx

import franken_networkx as fnx
import franken_networkx.readwrite as fnx_rw


def make_edges(nodes: int, edges: int, seed: int) -> list[tuple[int, int]]:
    rng = random.Random(seed)
    out: list[tuple[int, int]] = []
    for _ in range(edges):
        out.append((rng.randrange(nodes), rng.randrange(nodes)))
    return out


def make_graphs(nodes: int, edges: int, seed: int) -> tuple[Any, nx.Graph]:
    edge_list = make_edges(nodes, edges, seed)
    return fnx.Graph(edge_list), nx.Graph(edge_list)


def set_old_path() -> None:
    fnx_rw._write_gml_can_use_rust_int_noattr = lambda _graph, _stringizer: False


def write_once(kind: str, graph: Any, nx_graph: nx.Graph, path: Path) -> bytes:
    if kind == "fnx-after":
        fnx.write_gml(graph, path)
    elif kind == "fnx-before":
        set_old_path()
        fnx.write_gml(graph, path)
    elif kind == "nx":
        nx.write_gml(nx_graph, path)
    else:
        raise ValueError(kind)
    return path.read_bytes()


def bench(kind: str, nodes: int, edges: int, seed: int, loops: int, repeat: int) -> dict[str, Any]:
    graph, nx_graph = make_graphs(nodes, edges, seed)
    out_path = Path(f"/data/tmp/fnx_write_gml_fastpath_{kind}_{os.getpid()}.gml")
    times: list[float] = []
    digest = ""
    for _ in range(repeat):
        start = time.perf_counter()
        payload = b""
        for _ in range(loops):
            payload = write_once(kind, graph, nx_graph, out_path)
        elapsed = time.perf_counter() - start
        digest = hashlib.sha256(payload).hexdigest()
        times.append(elapsed / loops)
    return {
        "kind": kind,
        "nodes": nodes,
        "edges": graph.number_of_edges(),
        "loops": loops,
        "repeat": repeat,
        "best_seconds_per_write": min(times),
        "median_seconds_per_write": sorted(times)[len(times) // 2],
        "all_seconds_per_write": times,
        "digest": digest,
    }


def proof() -> dict[str, Any]:
    root = Path(tempfile.mkdtemp(prefix="fnx_wgml_", dir="/data/tmp"))
    failures: list[str] = []
    shas: list[str] = []

    cases: list[tuple[str, Any, Any]] = []
    for n in [0, 1, 2, 6, 30]:
        fg = fnx.path_graph(n)
        ng = nx.path_graph(n)
        cases.append((f"path-{n}", fg, ng))
    dg = fnx.DiGraph()
    dg.add_edges_from([(0, 1), (0, 2), (2, 1)])
    ndg = nx.DiGraph()
    ndg.add_edges_from([(0, 1), (0, 2), (2, 1)])
    cases.append(("digraph", dg, ndg))

    for name, fg, ng in cases:
        fp = root / f"{name}_fnx.gml"
        np = root / f"{name}_nx.gml"
        fnx.write_gml(fg, fp)
        nx.write_gml(ng, np)
        fb = fp.read_bytes()
        nb = np.read_bytes()
        if fb != nb:
            failures.append(f"{name}: fast path bytes diverged")
        shas.append(hashlib.sha256(fb).hexdigest())

    delegated_cases = []
    sg = fnx.Graph()
    sg.add_edge("a", "b")
    nsg = nx.Graph()
    nsg.add_edge("a", "b")
    delegated_cases.append(("string-labels", sg, nsg))
    ag = fnx.Graph()
    ag.add_edge(1, 2, weight=3)
    nag = nx.Graph()
    nag.add_edge(1, 2, weight=3)
    delegated_cases.append(("edge-attrs", ag, nag))

    for name, fg, ng in delegated_cases:
        fp = root / f"{name}_fnx.gml"
        np = root / f"{name}_nx.gml"
        fnx.write_gml(fg, fp)
        nx.write_gml(ng, np)
        fb = fp.read_bytes()
        nb = np.read_bytes()
        if fb != nb:
            failures.append(f"{name}: delegated bytes diverged")
        shas.append(hashlib.sha256(fb).hexdigest())

    golden = hashlib.sha256("".join(shas).encode("ascii")).hexdigest()
    return {"cases": len(shas), "failures": failures, "golden_sha256": golden, "tmp": str(root)}


def profile(kind: str, nodes: int, edges: int, seed: int, loops: int, output: Path) -> dict[str, Any]:
    graph, nx_graph = make_graphs(nodes, edges, seed)
    out_path = Path(f"/data/tmp/fnx_write_gml_fastpath_profile_{kind}_{os.getpid()}.gml")

    def run() -> None:
        for _ in range(loops):
            write_once(kind, graph, nx_graph, out_path)

    profiler = cProfile.Profile()
    profiler.runcall(run)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as handle:
        pstats.Stats(profiler, stream=handle).strip_dirs().sort_stats("cumtime").print_stats(50)
    return {"kind": kind, "loops": loops, "profile": str(output)}


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)

    bench_parser = sub.add_parser("bench")
    bench_parser.add_argument("--kind", choices=["fnx-before", "fnx-after", "nx"], required=True)
    bench_parser.add_argument("--nodes", type=int, default=3000)
    bench_parser.add_argument("--edges", type=int, default=9000)
    bench_parser.add_argument("--seed", type=int, default=1)
    bench_parser.add_argument("--loops", type=int, default=1)
    bench_parser.add_argument("--repeat", type=int, default=5)

    sub.add_parser("proof")

    prof = sub.add_parser("profile")
    prof.add_argument("--kind", choices=["fnx-before", "fnx-after", "nx"], required=True)
    prof.add_argument("--nodes", type=int, default=3000)
    prof.add_argument("--edges", type=int, default=9000)
    prof.add_argument("--seed", type=int, default=1)
    prof.add_argument("--loops", type=int, default=3)
    prof.add_argument("--output", type=Path, required=True)

    args = parser.parse_args(argv)
    if args.cmd == "bench":
        print(json.dumps(bench(args.kind, args.nodes, args.edges, args.seed, args.loops, args.repeat), sort_keys=True))
        return 0
    if args.cmd == "proof":
        result = proof()
        print(json.dumps(result, sort_keys=True))
        return 1 if result["failures"] else 0
    if args.cmd == "profile":
        print(json.dumps(profile(args.kind, args.nodes, args.edges, args.seed, args.loops, args.output), sort_keys=True))
        return 0
    raise AssertionError(args.cmd)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
