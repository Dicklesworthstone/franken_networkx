#!/usr/bin/env python3
"""Benchmark and parity harness for directed single_target_shortest_path_length."""

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


def build_graph(n: int = 2500, fanout: int = 4):
    graph = fnx.DiGraph()
    graph.add_nodes_from(range(n))
    for node in range(n - 1):
        graph.add_edge(node, node + 1)
        for step in range(2, fanout + 1):
            target = node + step
            if target < n:
                graph.add_edge(node, target)

    nx_graph = nx.DiGraph()
    nx_graph.add_nodes_from(range(n))
    nx_graph.add_edges_from(graph.edges())
    return graph, nx_graph, n - 1


def old_python_reverse_bfs(graph, target, cutoff=None):
    if cutoff is None:
        cutoff = float("inf")
    seen = {target}
    nextlevel = [target]
    level = 0
    lengths = {target: level}
    node_count = len(graph)
    while nextlevel and cutoff > level:
        level += 1
        thislevel = nextlevel
        nextlevel = []
        for node in thislevel:
            for neighbor in graph.predecessors(node):
                if neighbor not in seen:
                    seen.add(neighbor)
                    nextlevel.append(neighbor)
                    lengths[neighbor] = level
            if len(seen) == node_count:
                return lengths
    return lengths


def run(mode: str, repeats: int, n: int, fanout: int, cutoff):
    graph, nx_graph, target = build_graph(n=n, fanout=fanout)
    if mode == "old":
        fn = lambda: old_python_reverse_bfs(graph, target, cutoff=cutoff)
    elif mode == "fnx":
        fn = lambda: fnx.single_target_shortest_path_length(
            graph, target, cutoff=cutoff
        )
    elif mode == "nx":
        fn = lambda: nx.single_target_shortest_path_length(
            nx_graph, target, cutoff=cutoff
        )
    else:
        raise ValueError(mode)

    start = time.perf_counter()
    result = None
    for _ in range(repeats):
        result = fn()
    elapsed = time.perf_counter() - start
    assert result is not None
    normalized = list(result.items())
    digest = hashlib.sha256(
        json.dumps(normalized, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()
    print(
        json.dumps(
            {
                "mode": mode,
                "n": n,
                "fanout": fanout,
                "cutoff": cutoff,
                "repeats": repeats,
                "elapsed": elapsed,
                "per_call": elapsed / repeats,
                "len": len(result),
                "digest": digest,
                "head": normalized[:8],
                "tail": normalized[-8:],
            },
            sort_keys=True,
        )
    )


def golden(n: int, fanout: int, cutoff):
    graph, nx_graph, target = build_graph(n=n, fanout=fanout)
    cases = {
        "old": old_python_reverse_bfs(graph, target, cutoff=cutoff),
        "fnx": fnx.single_target_shortest_path_length(
            graph, target, cutoff=cutoff
        ),
        "nx": nx.single_target_shortest_path_length(
            nx_graph, target, cutoff=cutoff
        ),
        "fnx_cutoff_3": fnx.single_target_shortest_path_length(
            graph, target, cutoff=3
        ),
        "nx_cutoff_3": nx.single_target_shortest_path_length(
            nx_graph, target, cutoff=3
        ),
    }
    payload = {name: list(value.items()) for name, value in cases.items()}
    for left, right in [
        ("old", "fnx"),
        ("old", "nx"),
        ("fnx_cutoff_3", "nx_cutoff_3"),
    ]:
        if payload[left] != payload[right]:
            raise AssertionError(f"{left} != {right}")
    blob = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    print(hashlib.sha256(blob).hexdigest())
    print(json.dumps(payload, separators=(",", ":"), sort_keys=True))


def profile(mode: str, repeats: int, n: int, fanout: int, cutoff, output: Path):
    profiler = cProfile.Profile()
    profiler.enable()
    run(mode, repeats=repeats, n=n, fanout=fanout, cutoff=cutoff)
    profiler.disable()
    with output.open("w", encoding="utf-8") as handle:
        stats = pstats.Stats(profiler, stream=handle)
        stats.strip_dirs().sort_stats("cumtime").print_stats(40)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["old", "fnx", "nx", "golden", "profile"])
    parser.add_argument("--profile-mode", choices=["old", "fnx", "nx"], default="fnx")
    parser.add_argument("--profile-output", type=Path)
    parser.add_argument("--repeats", type=int, default=200)
    parser.add_argument("--n", type=int, default=2500)
    parser.add_argument("--fanout", type=int, default=4)
    parser.add_argument("--cutoff", type=int)
    args = parser.parse_args()

    if args.mode == "golden":
        golden(n=args.n, fanout=args.fanout, cutoff=args.cutoff)
    elif args.mode == "profile":
        if args.profile_output is None:
            raise SystemExit("--profile-output is required for profile mode")
        profile(
            args.profile_mode,
            repeats=args.repeats,
            n=args.n,
            fanout=args.fanout,
            cutoff=args.cutoff,
            output=args.profile_output,
        )
    else:
        run(args.mode, repeats=args.repeats, n=args.n, fanout=args.fanout, cutoff=args.cutoff)


if __name__ == "__main__":
    main()
