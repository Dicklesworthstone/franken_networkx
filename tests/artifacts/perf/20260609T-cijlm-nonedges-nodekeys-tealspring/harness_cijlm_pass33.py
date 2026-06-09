#!/usr/bin/env python3
"""cijlm pass 33 proof/bench harness for node-key caller adoption."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

import franken_networkx as fnx
import networkx as nx


def _build(module, graph_type: str, n: int, step: int):
    cls = getattr(module, graph_type)
    graph = cls()
    graph.add_nodes_from(range(n))
    for u in range(n):
        graph.add_edge(u, (u + 1) % n)
        graph.add_edge(u, (u + step) % n)
    if graph_type.startswith("Multi"):
        for u in range(0, n, 7):
            graph.add_edge(u, (u + step + 3) % n, key=f"k{u}")
    return graph


def _proof_payload() -> dict[str, object]:
    cases = []
    for graph_type, n, step in (
        ("DiGraph", 9, 3),
        ("MultiDiGraph", 9, 4),
        ("Graph", 8, 3),
        ("MultiGraph", 8, 4),
    ):
        fg = _build(fnx, graph_type, n, step)
        ng = _build(nx, graph_type, n, step)
        for node in (0, n // 2):
            fnx_non_neighbors = list(fnx.non_neighbors(fg, node))
            nx_non_neighbors = list(nx.non_neighbors(ng, node))
            cases.append(
                {
                    "graph_type": graph_type,
                    "node": node,
                    "kind": "non_neighbors",
                    "fnx": fnx_non_neighbors,
                    "nx": nx_non_neighbors,
                    "match": fnx_non_neighbors == nx_non_neighbors,
                }
            )
        fnx_non_edges = list(fnx.non_edges(fg))
        nx_non_edges = list(nx.non_edges(ng))
        cases.append(
            {
                "graph_type": graph_type,
                "kind": "non_edges",
                "fnx": fnx_non_edges,
                "nx": nx_non_edges,
                "match": fnx_non_edges == nx_non_edges,
            }
        )
    payload = {
        "cases": cases,
        "all_match": all(case["match"] for case in cases),
        "ordering": "exact list order compared to NetworkX",
        "tie_breaking": "CPython set difference order preserved by exact output comparison",
        "floating_point": "N/A",
        "rng": "N/A",
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    payload["sha256"] = hashlib.sha256(encoded).hexdigest()
    return payload


def _bench(module, graph_type: str, n: int, step: int, loops: int) -> dict[str, object]:
    graph = _build(module, graph_type, n, step)
    non_edges_count = 0
    non_neighbors_count = 0
    t0 = time.perf_counter()
    for _ in range(loops):
        non_edges_count += sum(1 for _ in module.non_edges(graph))
    t1 = time.perf_counter()
    for _ in range(loops):
        for node in range(0, n, max(1, n // 64)):
            non_neighbors_count += len(list(module.non_neighbors(graph, node)))
    t2 = time.perf_counter()
    return {
        "impl": module.__name__,
        "graph_type": graph_type,
        "n": n,
        "step": step,
        "loops": loops,
        "non_edges_seconds": t1 - t0,
        "non_neighbors_seconds": t2 - t1,
        "non_edges_count": non_edges_count,
        "non_neighbors_count": non_neighbors_count,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("proof", "bench"))
    parser.add_argument("--impl", choices=("fnx", "nx", "both"), default="both")
    parser.add_argument("--graph-type", default="DiGraph")
    parser.add_argument("--n", type=int, default=750)
    parser.add_argument("--step", type=int, default=17)
    parser.add_argument("--loops", type=int, default=3)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    if args.mode == "proof":
        payload = _proof_payload()
    else:
        impls = (("fnx", fnx), ("nx", nx)) if args.impl == "both" else ((args.impl, fnx if args.impl == "fnx" else nx),)
        payload = {
            name: _bench(module, args.graph_type, args.n, args.step, args.loops)
            for name, module in impls
        }

    text = json.dumps(payload, indent=2, sort_keys=True)
    if args.out is not None:
        args.out.write_text(text + "\n", encoding="utf-8")
    if not args.quiet:
        print(text)


if __name__ == "__main__":
    main()
