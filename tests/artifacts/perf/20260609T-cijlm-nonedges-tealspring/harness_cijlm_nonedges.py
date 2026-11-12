#!/usr/bin/env python3
"""cijlm non_edges node-key benchmark/proof harness."""

from __future__ import annotations

import argparse
import cProfile
import hashlib
import json
import pstats
import time
from pathlib import Path

import franken_networkx as fnx
import networkx as nx


def make_directed(factory, n: int, multigraph: bool = False):
    graph = factory()
    graph.add_nodes_from(range(n))
    for i in range(n):
        graph.add_edge(i, (i + 1) % n)
        graph.add_edge(i, (i + 7) % n)
        if multigraph:
            graph.add_edge(i, (i + 13) % n, key=f"k{i}")
        else:
            graph.add_edge(i, (i + 13) % n)
    return graph


def make_undirected(factory, n: int, multigraph: bool = False):
    graph = factory()
    graph.add_nodes_from(range(n))
    for i in range(n):
        graph.add_edge(i, (i + 1) % n)
        graph.add_edge(i, (i + 5) % n)
        if multigraph:
            graph.add_edge(i, (i + 9) % n, key=f"k{i}")
        else:
            graph.add_edge(i, (i + 9) % n)
    return graph


def proof_payload(n: int):
    cases = [
        ("digraph", make_directed(fnx.DiGraph, n), make_directed(nx.DiGraph, n)),
        (
            "multidigraph",
            make_directed(fnx.MultiDiGraph, n, multigraph=True),
            make_directed(nx.MultiDiGraph, n, multigraph=True),
        ),
        ("graph", make_undirected(fnx.Graph, n), make_undirected(nx.Graph, n)),
        (
            "multigraph",
            make_undirected(fnx.MultiGraph, n, multigraph=True),
            make_undirected(nx.MultiGraph, n, multigraph=True),
        ),
    ]
    rows = []
    for name, fg, ng in cases:
        fnx_edges = list(fnx.non_edges(fg))
        nx_edges = list(nx.non_edges(ng))
        rows.append(
            {
                "case": name,
                "count": len(fnx_edges),
                "matches_nx": fnx_edges == nx_edges,
                "head": fnx_edges[:16],
                "tail": fnx_edges[-16:],
            }
        )
    return rows


def timed(fn, loops: int):
    samples = []
    total = 0
    for _ in range(loops):
        start = time.perf_counter()
        total = fn()
        samples.append(time.perf_counter() - start)
    samples_sorted = sorted(samples)
    return {
        "total": total,
        "samples": samples,
        "min": samples_sorted[0],
        "median": samples_sorted[len(samples_sorted) // 2],
        "mean": sum(samples) / len(samples),
    }


def timing_payload(n: int, loops: int):
    cases = [
        ("digraph", make_directed(fnx.DiGraph, n), make_directed(nx.DiGraph, n)),
        (
            "multidigraph",
            make_directed(fnx.MultiDiGraph, n, multigraph=True),
            make_directed(nx.MultiDiGraph, n, multigraph=True),
        ),
    ]
    rows = []
    for name, fg, ng in cases:
        rows.append(
            {
                "case": name,
                "fnx": timed(lambda graph=fg: sum(1 for _ in fnx.non_edges(graph)), loops),
                "nx": timed(lambda graph=ng: sum(1 for _ in nx.non_edges(graph)), loops),
            }
        )
    return rows


def sha_payload(payload) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("proof", "time", "profile"), required=True)
    parser.add_argument("--n", type=int, default=320)
    parser.add_argument("--loops", type=int, default=5)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    if args.mode == "proof":
        payload = {"proof": proof_payload(args.n)}
        payload["sha256"] = sha_payload(payload["proof"])
    elif args.mode == "time":
        payload = {"timing": timing_payload(args.n, args.loops)}
        payload["sha256"] = sha_payload(payload["timing"])
    else:
        graph = make_directed(fnx.MultiDiGraph, args.n, multigraph=True)
        profiler = cProfile.Profile()
        profiler.enable()
        total = sum(1 for _ in fnx.non_edges(graph))
        profiler.disable()
        stats_path = args.out if args.out else Path("profile.txt")
        with stats_path.open("w", encoding="utf-8") as fh:
            pstats.Stats(profiler, stream=fh).sort_stats("cumtime").print_stats(35)
        payload = {"profile_path": str(stats_path), "total": total}

    if args.mode != "profile":
        text = json.dumps(payload, sort_keys=True, indent=2)
        if args.out:
            args.out.write_text(text + "\n", encoding="utf-8")
        print(text)
    else:
        print(json.dumps(payload, sort_keys=True))


if __name__ == "__main__":
    main()
