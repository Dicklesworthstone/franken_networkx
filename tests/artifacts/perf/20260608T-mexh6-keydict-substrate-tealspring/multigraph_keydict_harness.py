#!/usr/bin/env python3
"""Perf/proof harness for br-r37-c1-mexh6 MultiGraph keydict substrate."""

from __future__ import annotations

import argparse
import cProfile
import hashlib
import json
import pstats
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
PYTHON = ROOT / "python"
for path in (str(ROOT), str(PYTHON)):
    while path in sys.path:
        sys.path.remove(path)
    sys.path.insert(0, path)

import franken_networkx as fnx  # noqa: E402
import networkx as nx  # noqa: E402


def build_graph(module, *, directed: bool, nodes: int, degree: int, parallel: int):
    graph = (module.MultiDiGraph if directed else module.MultiGraph)()
    graph.add_nodes_from(range(nodes))
    for u in range(nodes):
        for step in range(1, degree + 1):
            v = (u + step) % nodes
            if not directed and u > v:
                continue
            for key in range(parallel):
                graph.add_edge(u, v, key=f"k{key}", weight=u + v + key, tag=f"{u}:{v}:{key}")
    graph.add_edge(0, 0, key="loop", weight=7, tag="loop")
    return graph


def canonicalize(result, graph, *, directed: bool):
    rows = []
    alias_pairs = 0
    live_mutations = 0
    for u, nbrs in result.items():
        row = []
        for v, keydict in nbrs.items():
            entries = []
            for key, attrs in keydict.items():
                entries.append((repr(key), tuple((repr(k), repr(vv)) for k, vv in attrs.items())))
                if graph[u][v][key] is attrs:
                    live_mutations += 1
            if not directed and u != v and v in result and u in result[v]:
                if result[u][v] is result[v][u]:
                    alias_pairs += 1
            row.append((repr(v), entries))
        rows.append((repr(u), row))
    payload = {
        "rows": rows,
        "alias_pairs": alias_pairs,
        "live_mutations": live_mutations,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest(), payload


def run_case(module_name: str, *, directed: bool, nodes: int, degree: int, parallel: int, repeats: int):
    module = fnx if module_name == "fnx" else nx
    graph = build_graph(module, directed=directed, nodes=nodes, degree=degree, parallel=parallel)
    start = time.perf_counter()
    result = None
    for _ in range(repeats):
        result = module.to_dict_of_dicts(graph)
    elapsed = time.perf_counter() - start
    digest, payload = canonicalize(result, graph, directed=directed)
    return {
        "module": module_name,
        "directed": directed,
        "nodes": nodes,
        "degree": degree,
        "parallel": parallel,
        "repeats": repeats,
        "elapsed": elapsed,
        "sha256": digest,
        "alias_pairs": payload["alias_pairs"],
        "live_mutations": payload["live_mutations"],
        "node_count": len(result),
        "row_count": sum(len(row) for row in result.values()),
        "edge_count": graph.number_of_edges(),
    }


def run_proof(args):
    cases = []
    for directed in (False, True):
        fnx_result = run_case(
            "fnx",
            directed=directed,
            nodes=args.nodes,
            degree=args.degree,
            parallel=args.parallel,
            repeats=1,
        )
        nx_result = run_case(
            "nx",
            directed=directed,
            nodes=args.nodes,
            degree=args.degree,
            parallel=args.parallel,
            repeats=1,
        )
        cases.append(
            {
                "directed": directed,
                "fnx": fnx_result,
                "nx": nx_result,
                "matches_nx": fnx_result["sha256"] == nx_result["sha256"]
                and fnx_result["alias_pairs"] == nx_result["alias_pairs"]
                and fnx_result["live_mutations"] == nx_result["live_mutations"],
            }
        )
    payload = {
        "cases": cases,
        "ordering_preserved": all(case["matches_nx"] for case in cases),
        "tie_breaking": "N/A: no algorithmic tie-break path",
        "floating_point": "N/A: attributes are serialized only",
        "rng": "N/A: deterministic synthetic graph",
    }
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    payload["sha256"] = digest
    Path(args.output).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(json.dumps(payload, sort_keys=True))


def run_timing(args):
    fnx_result = run_case(
        "fnx",
        directed=args.directed,
        nodes=args.nodes,
        degree=args.degree,
        parallel=args.parallel,
        repeats=args.repeats,
    )
    nx_result = run_case(
        "nx",
        directed=args.directed,
        nodes=args.nodes,
        degree=args.degree,
        parallel=args.parallel,
        repeats=args.repeats,
    )
    payload = {"fnx": fnx_result, "nx": nx_result, "ratio": fnx_result["elapsed"] / nx_result["elapsed"]}
    Path(args.output).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(json.dumps(payload, sort_keys=True))


def run_profile(args):
    profiler = cProfile.Profile()
    profiler.enable()
    result = run_case(
        "fnx",
        directed=args.directed,
        nodes=args.nodes,
        degree=args.degree,
        parallel=args.parallel,
        repeats=args.repeats,
    )
    profiler.disable()
    with Path(args.output).open("w", encoding="utf-8") as handle:
        stats = pstats.Stats(profiler, stream=handle).strip_dirs().sort_stats("cumtime")
        stats.print_stats(35)
        handle.write("\nRESULT ")
        handle.write(json.dumps(result, sort_keys=True))
        handle.write("\n")
    print(json.dumps(result, sort_keys=True))


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    for name in ("proof", "timing", "profile"):
        cmd = sub.add_parser(name)
        cmd.add_argument("--nodes", type=int, default=1200)
        cmd.add_argument("--degree", type=int, default=5)
        cmd.add_argument("--parallel", type=int, default=3)
        cmd.add_argument("--repeats", type=int, default=80)
        cmd.add_argument("--directed", action="store_true")
        cmd.add_argument("--output", required=True)
    args = parser.parse_args()
    if args.cmd == "proof":
        run_proof(args)
    elif args.cmd == "timing":
        run_timing(args)
    elif args.cmd == "profile":
        run_profile(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
