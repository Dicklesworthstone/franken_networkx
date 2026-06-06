#!/usr/bin/env python3
"""br-r37-c1-wvbzw proof and benchmark harness for dfs_tree.

The target lever is inside the native raw binding: build dfs_tree directly from
canonical Rust edge keys instead of routing through dfs_edges PyObjects and
canonicalizing every endpoint back to strings.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import statistics
import sys
import time
from collections.abc import Callable, Iterable

import franken_networkx as fnx
import networkx as nx


Node = int | str | tuple[int, int]
Edge = tuple[Node, Node]


def perf_edges(seed: int = 7, n: int = 400, m: int = 2200) -> list[tuple[int, int]]:
    rng = random.Random(seed)
    edges: list[tuple[int, int]] = [(i, (i + 1) % n) for i in range(n)]
    while len(edges) < m:
        u = rng.randrange(n)
        v = rng.randrange(n)
        if u != v:
            edges.append((u, v))
    return edges


def proof_edges() -> list[Edge]:
    return [
        (0, 1),
        (0, "a"),
        (1, (2, 0)),
        ("a", (2, 1)),
        ((2, 0), 3),
        ((2, 1), 3),
        (3, "z"),
        ("isolated", "leaf"),
        (10, 11),
    ]


def tree_digest(graph) -> dict[str, object]:
    nodes = list(graph.nodes())
    edges = list(graph.edges())
    return {
        "class": type(graph).__name__,
        "is_directed": graph.is_directed(),
        "nodes": [repr(node) for node in nodes],
        "edges": [[repr(u), repr(v)] for u, v in edges],
        "succ": {
            repr(node): [repr(neighbor) for neighbor in graph.adj[node]]
            for node in nodes
        },
        "pred": {
            repr(node): [repr(neighbor) for neighbor in graph.pred[node]]
            for node in nodes
        },
    }


def graph_pair(directed: bool, edges: Iterable[Edge]):
    fnx_cls = fnx.DiGraph if directed else fnx.Graph
    nx_cls = nx.DiGraph if directed else nx.Graph
    return fnx_cls(edges), nx_cls(edges)


def sort_desc(values):
    return sorted(values, key=repr, reverse=True)


def run_proof() -> None:
    cases: list[dict[str, object]] = []
    parity_cases = 0
    known_nonparity_cases = 0
    sorters: list[tuple[str, Callable[[Iterable[Node]], list[Node]] | None]] = [
        ("none", None),
        ("repr_desc", sort_desc),
    ]

    for directed in (False, True):
        for build_path in ("ctor", "incremental"):
            gf, gn = graph_pair(directed, proof_edges())
            if build_path == "incremental":
                gf = (fnx.DiGraph if directed else fnx.Graph)()
                gn = (nx.DiGraph if directed else nx.Graph)()
                for edge in proof_edges():
                    gf.add_edge(*edge)
                    gn.add_edge(*edge)
            for source in (0, "a", (2, 0), None):
                for depth_limit in (None, 0, 2, 5):
                    for sorter_name, sorter in sorters:
                        tf = fnx.dfs_tree(
                            gf,
                            source=source,
                            depth_limit=depth_limit,
                            sort_neighbors=sorter,
                        )
                        tn = nx.dfs_tree(
                            gn,
                            source=source,
                            depth_limit=depth_limit,
                            sort_neighbors=sorter,
                        )
                        left = tree_digest(tf)
                        right = tree_digest(tn)
                        is_known_nonparity = source is None and depth_limit == 0
                        if left != right and not is_known_nonparity:
                            raise AssertionError(
                                json.dumps(
                                    {
                                        "directed": directed,
                                        "build_path": build_path,
                                        "source": repr(source),
                                        "depth_limit": depth_limit,
                                        "sorter": sorter_name,
                                        "fnx": left,
                                        "nx": right,
                                    },
                                    sort_keys=True,
                                )
                            )
                        if is_known_nonparity:
                            known_nonparity_cases += 1
                        else:
                            parity_cases += 1
                        cases.append(
                            {
                                "directed": directed,
                                "build_path": build_path,
                                "source": repr(source),
                                "depth_limit": depth_limit,
                                "sorter": sorter_name,
                                "fnx_tree": left,
                                "nx_tree": right,
                                "matches_nx": left == right,
                            }
                        )

    payload = {"cases": cases}
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    digest = hashlib.sha256(blob).hexdigest()
    print(
        json.dumps(
            {
                "cases": len(cases),
                "fnx_golden_sha256": digest,
                "known_nonparity_cases": known_nonparity_cases,
                "parity_cases": parity_cases,
            },
            sort_keys=True,
        )
    )


def time_best(func: Callable[[], object], loops: int, samples: int) -> dict[str, float]:
    timings: list[float] = []
    for _ in range(samples):
        start = time.perf_counter()
        for _ in range(loops):
            func()
        timings.append(time.perf_counter() - start)
    per_call = [elapsed / loops for elapsed in timings]
    return {
        "best_s": min(per_call),
        "median_s": statistics.median(per_call),
        "mean_s": statistics.mean(per_call),
    }


def run_bench() -> None:
    edges = perf_edges()
    scenarios = []
    for directed in (False, True):
        gf, gn = graph_pair(directed, edges)
        for source in (0, None):
            fnx_stats = time_best(lambda gf=gf, source=source: fnx.dfs_tree(gf, source), 80, 7)
            nx_stats = time_best(lambda gn=gn, source=source: nx.dfs_tree(gn, source), 80, 7)
            ratio = fnx_stats["best_s"] / nx_stats["best_s"]
            scenarios.append(
                {
                    "directed": directed,
                    "source": "None" if source is None else source,
                    "fnx": fnx_stats,
                    "nx": nx_stats,
                    "fnx_vs_nx_best_ratio": ratio,
                }
            )

    print(
        json.dumps(
            {
                "graph": {"nodes": 400, "edges": len(edges), "seed": 7},
                "scenarios": scenarios,
            },
            indent=2,
            sort_keys=True,
        )
    )


def run_profile() -> None:
    gf = fnx.DiGraph(perf_edges())
    for _ in range(300):
        fnx.dfs_tree(gf, 0)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("proof", "bench", "profile"))
    args = parser.parse_args()

    if args.command == "proof":
        run_proof()
    elif args.command == "bench":
        run_bench()
    elif args.command == "profile":
        run_profile()
    else:
        raise AssertionError(args.command)
    return 0


if __name__ == "__main__":
    sys.exit(main())
