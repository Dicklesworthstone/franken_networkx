#!/usr/bin/env python3
"""Proof and timing harness for br-r37-c1-5ib9p."""

from __future__ import annotations

import argparse
import cProfile
import hashlib
import json
import pstats
import statistics
import time
from pathlib import Path

import franken_networkx as fnx
import networkx as nx


ROOT = Path(__file__).resolve().parent


def _edges(n: int):
    edges = []
    for i in range(1, n):
        edges.append(((i * 37 + 11) % i, i))
    for i in range(n):
        j = (i * 97 + 53) % n
        if i != j:
            edges.append((i, j))
    return edges


def _build(module, n: int, *, attrs: bool = False):
    graph = module.Graph()
    graph.add_nodes_from(range(n))
    if attrs:
        for node in range(0, n, 7):
            graph.nodes[node]["color"] = f"c{node % 5}"
    for u, v in _edges(n):
        if attrs and (u + v) % 11 == 0:
            graph.add_edge(u, v, weight=(u * 17 + v * 31) % 13)
        else:
            graph.add_edge(u, v)
    graph.graph["name"] = "relabel-proof"
    return graph


def _mapping(n: int):
    return {i: i + 1 for i in range(0, n, 5)}


def _noncolliding_mapping(n: int):
    return {i: i + n + 1 for i in range(0, n, 5)}


def _signature(graph):
    nodes = [
        [repr(node), sorted((repr(k), repr(v)) for k, v in graph.nodes[node].items())]
        for node in graph.nodes()
    ]
    edges = [
        [
            repr(u),
            repr(v),
            sorted((repr(k), repr(vv)) for k, vv in attrs.items()),
        ]
        for u, v, attrs in graph.edges(data=True)
    ]
    return {
        "graph": sorted((repr(k), repr(v)) for k, v in graph.graph.items()),
        "nodes": nodes,
        "edges": edges,
    }


def _digest(signature) -> str:
    payload = json.dumps(signature, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()


def _run(module, n: int, *, attrs: bool = False, noncolliding: bool = False):
    graph = _build(module, n, attrs=attrs)
    mapping = _noncolliding_mapping(n) if noncolliding else _mapping(n)
    return module.relabel_nodes(graph, mapping, copy=True)


def proof(label: str, n: int, compare: Path | None) -> None:
    previous = json.loads(compare.read_text()) if compare is not None else None
    out = {"label": label, "n": n, "cases": {}}
    cases = [
        ("target_empty", n, False, False, True),
        ("small_attrs_no_collision", 80, True, True, True),
        ("small_attrs_collision_existing_behavior", 80, True, False, False),
        ("small_empty", 80, False, False, True),
    ]
    for name, case_n, attrs, noncolliding, require_nx_match in cases:
        actual = _run(fnx, case_n, attrs=attrs, noncolliding=noncolliding)
        expected = _run(nx, case_n, attrs=attrs, noncolliding=noncolliding)
        actual_sig = _signature(actual)
        expected_sig = _signature(expected)
        matches_nx = actual_sig == expected_sig
        if require_nx_match and not matches_nx:
            raise AssertionError(f"{name}: signature differs")
        actual_sha = _digest(actual_sig)
        case_out = {
            "fnx_sha256": actual_sha,
            "nx_sha256": _digest(expected_sig),
            "fnx_matches_nx": matches_nx,
            "node_count": actual.number_of_nodes(),
            "edge_count": actual.number_of_edges(),
        }
        if previous is not None:
            baseline_sha = previous["cases"][name]["fnx_sha256"]
            case_out["baseline_fnx_sha256"] = baseline_sha
            case_out["baseline_fnx_sha256_equal"] = actual_sha == baseline_sha
            if actual_sha != baseline_sha:
                raise AssertionError(f"{name}: golden sha changed")
        out["cases"][name] = case_out
    proof_path = ROOT / f"{label}_proof.json"
    proof_path.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")
    (ROOT / f"{label}_proof.sha256").write_text(
        hashlib.sha256(proof_path.read_bytes()).hexdigest() + "\n"
    )


def bench(label: str, n: int, samples: int) -> None:
    out = {"label": label, "n": n, "samples": samples, "cases": {}}
    for lib_name, module in (("fnx", fnx), ("nx", nx)):
        graph = _build(module, n)
        mapping = _mapping(n)
        values = []
        for _ in range(samples):
            start = time.perf_counter()
            module.relabel_nodes(graph, mapping, copy=True)
            values.append(time.perf_counter() - start)
        out["cases"][lib_name] = {
            "best": min(values),
            "median": statistics.median(values),
            "samples": values,
        }
    out["fnx_vs_nx_best_ratio"] = out["cases"]["fnx"]["best"] / out["cases"]["nx"]["best"]
    out["fnx_vs_nx_median_ratio"] = (
        out["cases"]["fnx"]["median"] / out["cases"]["nx"]["median"]
    )
    (ROOT / f"{label}_direct.json").write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")


def profile(label: str, n: int, reps: int) -> None:
    graph = _build(fnx, n)
    mapping = _mapping(n)

    def run():
        for _ in range(reps):
            fnx.relabel_nodes(graph, mapping, copy=True)

    profiler = cProfile.Profile()
    profiler.enable()
    run()
    profiler.disable()
    with (ROOT / f"{label}_profile.txt").open("w") as fh:
        pstats.Stats(profiler, stream=fh).strip_dirs().sort_stats("cumtime").print_stats(80)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["proof", "bench", "profile"])
    parser.add_argument("--label", required=True)
    parser.add_argument("--n", type=int, default=1800)
    parser.add_argument("--samples", type=int, default=7)
    parser.add_argument("--profile-reps", type=int, default=80)
    parser.add_argument("--compare", type=Path)
    args = parser.parse_args()
    if args.command == "proof":
        proof(args.label, args.n, args.compare)
    elif args.command == "bench":
        bench(args.label, args.n, args.samples)
    else:
        profile(args.label, args.n, args.profile_reps)


if __name__ == "__main__":
    main()
