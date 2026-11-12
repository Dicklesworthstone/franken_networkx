#!/usr/bin/env python3
"""Perf/proof harness for br-r37-c1-35cg6 DiGraph.add_edges_from batches."""

from __future__ import annotations

import argparse
import cProfile
import hashlib
import json
import pstats
import random
import statistics
import time
from pathlib import Path

import franken_networkx as fnx
import networkx as nx


ARTIFACT_DIR = Path(__file__).resolve().parent
DEFAULT_NODES = 1500
DEFAULT_EDGES = 5217
DEFAULT_LOOPS = 80
DEFAULT_SEED = 20260606


def make_edges(n: int, m: int, seed: int) -> list[tuple[object, object, dict[str, object]]]:
    rng = random.Random(seed)
    edges: list[tuple[object, object, dict[str, object]]] = []
    for i in range(m):
        u = rng.randrange(n)
        v = rng.randrange(n)
        # Deterministic attrs with enough variety to exercise merge and
        # AttrMap conversion without invoking non-replicable Python objects.
        attrs = {
            "weight": (i % 17) + (rng.randrange(1000) / 1000.0),
            "label": f"e{i % 31}",
            "flag": (i & 1) == 0,
        }
        # Deliberate duplicates near the tail: nx/fnx must merge attr dicts.
        if i % 113 == 0 and edges:
            old_u, old_v, _ = edges[rng.randrange(len(edges))]
            u = old_u
            v = old_v
            attrs["dupe"] = i
        edges.append((u, v, attrs))
    return edges


def build_fnx(edges: list[tuple[object, object, dict[str, object]]]) -> object:
    graph = fnx.DiGraph()
    graph.add_edges_from(edges)
    return graph


def build_nx(edges: list[tuple[object, object, dict[str, object]]]) -> object:
    graph = nx.DiGraph()
    graph.add_edges_from(edges)
    return graph


def edge_payload(graph: object) -> list[tuple[str, str, list[tuple[str, str]]]]:
    return [
        (
            repr(u),
            repr(v),
            sorted((str(k), repr(vv)) for k, vv in data.items()),
        )
        for u, v, data in graph.edges(data=True)
    ]


def graph_payload(graph: object) -> dict[str, object]:
    return {
        "nodes": [repr(node) for node in graph.nodes()],
        "edges": edge_payload(graph),
        "succ": [
            (repr(node), [repr(nbr) for nbr in graph.successors(node)])
            for node in graph.nodes()
        ],
        "pred": [
            (repr(node), [repr(nbr) for nbr in graph.predecessors(node)])
            for node in graph.nodes()
        ],
    }


def run_proof(args: argparse.Namespace) -> dict[str, object]:
    cases: list[dict[str, object]] = []
    for offset in range(args.cases):
        seed = args.seed + offset
        edges = make_edges(args.nodes, args.edges, seed)
        f_graph = build_fnx(edges)
        n_graph = build_nx(edges)
        f_payload = graph_payload(f_graph)
        n_payload = graph_payload(n_graph)
        cases.append(
            {
                "seed": seed,
                "nodes": args.nodes,
                "edges": args.edges,
                "match": f_payload == n_payload,
                "fnx": f_payload,
                "nx": n_payload,
            }
        )

    canonical = json.dumps(cases, sort_keys=True, separators=(",", ":")) + "\n"
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    mismatches = [case["seed"] for case in cases if not case["match"]]
    result = {
        "sha256": digest,
        "cases": len(cases),
        "mismatches": mismatches,
        "all_match": not mismatches,
    }
    (ARTIFACT_DIR / "golden_add_edges_batch.canonical.json").write_text(canonical)
    (ARTIFACT_DIR / "golden_add_edges_batch.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n"
    )
    (ARTIFACT_DIR / "golden_add_edges_batch.sha256").write_text(
        f"{digest}  golden_add_edges_batch.canonical.json\n"
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return result


def run_timing(args: argparse.Namespace) -> dict[str, object]:
    edges = make_edges(args.nodes, args.edges, args.seed)
    for _ in range(args.warmups):
        build_fnx(edges)
        build_nx(edges)

    fnx_times: list[float] = []
    nx_times: list[float] = []
    for _ in range(args.loops):
        start = time.perf_counter()
        build_fnx(edges)
        fnx_times.append(time.perf_counter() - start)

        start = time.perf_counter()
        build_nx(edges)
        nx_times.append(time.perf_counter() - start)

    result = {
        "nodes": args.nodes,
        "edges": args.edges,
        "loops": args.loops,
        "seed": args.seed,
        "fnx": summarize(fnx_times),
        "nx": summarize(nx_times),
        "ratio_median": statistics.median(fnx_times) / statistics.median(nx_times),
        "ratio_min": min(fnx_times) / min(nx_times),
    }
    Path(args.output).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return result


def summarize(values: list[float]) -> dict[str, float]:
    ordered = sorted(values)
    return {
        "min_s": ordered[0],
        "median_s": statistics.median(ordered),
        "p95_s": percentile(ordered, 0.95),
        "p99_s": percentile(ordered, 0.99),
    }


def percentile(ordered: list[float], q: float) -> float:
    index = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * q)))
    return ordered[index]


def run_profile(args: argparse.Namespace) -> None:
    edges = make_edges(args.nodes, args.edges, args.seed)
    profiler = cProfile.Profile()
    profiler.enable()
    for _ in range(args.loops):
        build_fnx(edges)
    profiler.disable()
    with Path(args.output).open("w") as fh:
        stats = pstats.Stats(profiler, stream=fh).sort_stats("cumulative")
        stats.print_stats(40)


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)

    timing = sub.add_parser("timing")
    timing.add_argument("--nodes", type=int, default=DEFAULT_NODES)
    timing.add_argument("--edges", type=int, default=DEFAULT_EDGES)
    timing.add_argument("--loops", type=int, default=DEFAULT_LOOPS)
    timing.add_argument("--warmups", type=int, default=8)
    timing.add_argument("--seed", type=int, default=DEFAULT_SEED)
    timing.add_argument("--output", default=str(ARTIFACT_DIR / "timing.json"))

    proof = sub.add_parser("proof")
    proof.add_argument("--nodes", type=int, default=320)
    proof.add_argument("--edges", type=int, default=900)
    proof.add_argument("--cases", type=int, default=8)
    proof.add_argument("--seed", type=int, default=DEFAULT_SEED)

    profile = sub.add_parser("profile")
    profile.add_argument("--nodes", type=int, default=DEFAULT_NODES)
    profile.add_argument("--edges", type=int, default=DEFAULT_EDGES)
    profile.add_argument("--loops", type=int, default=200)
    profile.add_argument("--seed", type=int, default=DEFAULT_SEED)
    profile.add_argument("--output", default=str(ARTIFACT_DIR / "cprofile_fnx.txt"))

    args = parser.parse_args()
    if args.cmd == "timing":
        run_timing(args)
    elif args.cmd == "proof":
        run_proof(args)
    elif args.cmd == "profile":
        run_profile(args)


if __name__ == "__main__":
    main()
