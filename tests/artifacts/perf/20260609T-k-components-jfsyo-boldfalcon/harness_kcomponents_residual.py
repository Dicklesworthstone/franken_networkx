#!/usr/bin/env python3
"""Baseline/profile harness for br-r37-c1-jfsyo k_components residual."""

from __future__ import annotations

import argparse
import cProfile
import hashlib
import json
import pstats
import statistics
import sys
import tempfile
import time
from collections.abc import Callable
from pathlib import Path

import franken_networkx as fnx
import networkx as nx


class ResidualFlowProbe(Exception):
    """Raised when a residual k_components path reaches flow computations."""


def genuine_nx_k_components(graph, flow_func=None):
    """Call NetworkX's real implementation without backend dispatch."""

    func = getattr(nx.k_components, "orig_func", nx.k_components)
    return func(graph, flow_func=flow_func)


def canonical(result):
    return [
        {
            "k": k,
            "value_type": type(value).__name__,
            "components": [
                {
                    "type": type(component).__name__,
                    "nodes": sorted(repr(node) for node in component),
                }
                for component in value
            ],
        }
        for k, value in result.items()
    ]


def graph_digest(graph) -> str:
    payload = {
        "nodes": sorted(repr(node) for node in graph.nodes()),
        "edges": sorted((repr(u), repr(v)) for u, v in graph.edges()),
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def result_digest(result) -> str:
    return hashlib.sha256(
        json.dumps(canonical(result), sort_keys=True).encode()
    ).hexdigest()


def chorded_cycle(lib, n: int):
    graph = lib.cycle_graph(n)
    for node in range(0, n, 4):
        graph.add_edge(node, (node + 2) % n)
    return graph


def paired_clique_barbell(lib, m: int):
    graph = lib.Graph()
    left = list(range(m))
    right = list(range(m, 2 * m))
    graph.add_nodes_from(left)
    graph.add_nodes_from(right)
    for nodes in (left, right):
        for i, u in enumerate(nodes):
            for v in nodes[i + 1 :]:
                graph.add_edge(u, v)
    graph.add_edge(0, m)
    graph.add_edge(1, m + 1)
    return graph


def near_barbell_bypass(lib, m: int):
    graph = lib.barbell_graph(m, 1)
    graph.add_edge(1, m + 2)
    return graph


def square_with_diagonal(lib, _size: int):
    graph = lib.Graph()
    graph.add_edges_from([(0, 1), (1, 2), (2, 3), (3, 0), (0, 2)])
    return graph


FAMILIES: dict[str, Callable[[object, int], object]] = {
    "chorded_cycle": chorded_cycle,
    "paired_clique_barbell": paired_clique_barbell,
    "near_barbell_bypass": near_barbell_bypass,
    "square_with_diagonal": square_with_diagonal,
}

DEFAULT_PROOF_CASES = [
    ("square_with_diagonal", 0),
    ("chorded_cycle", 12),
    ("chorded_cycle", 16),
    ("paired_clique_barbell", 8),
    ("near_barbell_bypass", 8),
]


def make_graph(which: str, family: str, size: int):
    try:
        builder = FAMILIES[family]
    except KeyError as exc:
        raise SystemExit(f"unknown family: {family}") from exc
    if which == "fnx":
        return builder(fnx, size)
    if which == "nx":
        return builder(nx, size)
    raise SystemExit(f"unknown implementation: {which}")


def residual_probe(which: str, family: str, size: int) -> dict[str, object]:
    def fail_flow(*_args, **_kwargs):
        raise ResidualFlowProbe("flow_func reached residual connectivity path")

    graph = make_graph(which, family, size)
    func = fnx.k_components if which == "fnx" else genuine_nx_k_components
    try:
        func(graph, flow_func=fail_flow)
    except ResidualFlowProbe as exc:
        return {"called": True, "exception": type(exc).__name__, "message": str(exc)}
    except Exception as exc:  # noqa: BLE001 - proof records observable surface.
        return {"called": False, "exception": type(exc).__name__, "message": str(exc)}
    return {"called": False, "exception": None, "message": None}


def case_record(family: str, size: int) -> dict[str, object]:
    fnx_graph = make_graph("fnx", family, size)
    nx_graph = make_graph("nx", family, size)
    fnx_result = fnx.k_components(fnx_graph)
    nx_result = genuine_nx_k_components(nx_graph)
    fnx_canonical = canonical(fnx_result)
    nx_canonical = canonical(nx_result)
    return {
        "family": family,
        "size": size,
        "nodes": fnx_graph.number_of_nodes(),
        "edges": fnx_graph.number_of_edges(),
        "graph_sha256": graph_digest(nx_graph),
        "fnx": fnx_canonical,
        "nx": nx_canonical,
        "match": fnx_canonical == nx_canonical,
        "key_order": list(fnx_result.keys()),
        "result_sha256": result_digest(fnx_result),
        "flow_probe": {
            "fnx": residual_probe("fnx", family, size),
            "nx": residual_probe("nx", family, size),
        },
    }


def proof(out: Path) -> None:
    rows = [case_record(family, size) for family, size in DEFAULT_PROOF_CASES]
    payload = {
        "bead": "br-r37-c1-jfsyo",
        "commit": "b5d463fc14dbd04a89494df6b8be3bb68d8a289b",
        "fnx_file": fnx.__file__,
        "nx_file": nx.__file__,
        "nx_version": nx.__version__,
        "genuine_networkx": "nx.k_components.orig_func",
        "cases": rows,
        "all_match": all(row["match"] for row in rows),
        "all_residual_flow_called": all(
            row["flow_probe"]["fnx"]["called"] and row["flow_probe"]["nx"]["called"]
            for row in rows
        ),
        "isomorphism": {
            "ordering_preserved": (
                "golden records k insertion order and component order; FNX matches "
                "genuine NetworkX orig_func for every residual case"
            ),
            "tie_breaking_unchanged": (
                "no new tie-break policy is introduced; all tested cases delegate "
                "to the Moody-White/Kanevsky residual path"
            ),
            "floating_point": "N/A: k_components emits integer node-set structures only",
            "rng": "N/A: graph builders are deterministic and unseeded randomness is unused",
        },
    }
    text = json.dumps(payload, sort_keys=True, indent=2)
    out.write_text(text + "\n", encoding="utf-8")
    print(hashlib.sha256((text + "\n").encode()).hexdigest())
    if not payload["all_match"] or not payload["all_residual_flow_called"]:
        raise SystemExit("proof mismatch or non-residual case detected")


def time_one(which: str, family: str, size: int, repeats: int) -> dict[str, object]:
    graph = make_graph(which, family, size)
    func = fnx.k_components if which == "fnx" else genuine_nx_k_components
    result = None
    start = time.perf_counter()
    for _ in range(repeats):
        result = func(graph)
    elapsed = time.perf_counter() - start
    return {
        "which": which,
        "family": family,
        "size": size,
        "nodes": graph.number_of_nodes(),
        "edges": graph.number_of_edges(),
        "repeats": repeats,
        "seconds": elapsed,
        "seconds_per_call": elapsed / repeats,
        "result_sha256": result_digest(result),
    }


def direct(out: Path, repeats: int) -> None:
    rows = []
    for family, size in [
        ("chorded_cycle", 12),
        ("chorded_cycle", 16),
        ("paired_clique_barbell", 8),
        ("near_barbell_bypass", 8),
    ]:
        samples = {"fnx": [], "nx": []}
        last = {}
        for _ in range(repeats):
            for which in ("fnx", "nx"):
                record = time_one(which, family, size, 1)
                samples[which].append(record["seconds_per_call"])
                last[which] = record
        rows.append(
            {
                "family": family,
                "size": size,
                "nodes": last["fnx"]["nodes"],
                "edges": last["fnx"]["edges"],
                "result_sha256": last["fnx"]["result_sha256"],
                "fnx_samples": samples["fnx"],
                "nx_samples": samples["nx"],
                "fnx_mean": statistics.mean(samples["fnx"]),
                "nx_mean": statistics.mean(samples["nx"]),
                "fnx_median": statistics.median(samples["fnx"]),
                "nx_median": statistics.median(samples["nx"]),
                "ratio_fnx_over_nx_mean": (
                    statistics.mean(samples["fnx"]) / statistics.mean(samples["nx"])
                ),
                "ratio_fnx_over_nx_median": (
                    statistics.median(samples["fnx"]) / statistics.median(samples["nx"])
                ),
            }
        )
    payload = {
        "bead": "br-r37-c1-jfsyo",
        "kind": "direct_baseline",
        "repeats": repeats,
        "python": sys.executable,
        "fnx_file": fnx.__file__,
        "nx_file": nx.__file__,
        "nx_version": nx.__version__,
        "genuine_networkx": "nx.k_components.orig_func",
        "rows": rows,
    }
    out.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def profile(which: str, family: str, size: int, repeats: int, out: Path) -> None:
    graph = make_graph(which, family, size)
    func = fnx.k_components if which == "fnx" else genuine_nx_k_components
    profiler = cProfile.Profile()
    profiler.enable()
    for _ in range(repeats):
        func(graph)
    profiler.disable()
    with tempfile.NamedTemporaryFile() as tmp:
        profiler.dump_stats(tmp.name)
        stats = pstats.Stats(tmp.name)
        stats.sort_stats("cumulative")
        with out.open("w", encoding="utf-8") as handle:
            handle.write(
                f"profile which={which} family={family} size={size} repeats={repeats}\n"
            )
            handle.write(f"fnx_file={fnx.__file__}\n")
            handle.write(f"nx_file={nx.__file__}\n")
            handle.write(f"nx_version={nx.__version__}\n\n")
            stats.stream = handle
            stats.print_stats(80)


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)

    proof_parser = sub.add_parser("proof")
    proof_parser.add_argument("--out", type=Path, required=True)

    direct_parser = sub.add_parser("direct")
    direct_parser.add_argument("--out", type=Path, required=True)
    direct_parser.add_argument("--repeats", type=int, default=3)

    time_parser = sub.add_parser("time")
    time_parser.add_argument("--which", choices=["fnx", "nx"], required=True)
    time_parser.add_argument("--family", choices=sorted(FAMILIES), default="chorded_cycle")
    time_parser.add_argument("--size", type=int, default=16)
    time_parser.add_argument("--repeats", type=int, default=1)

    profile_parser = sub.add_parser("profile")
    profile_parser.add_argument("--which", choices=["fnx", "nx"], required=True)
    profile_parser.add_argument("--family", choices=sorted(FAMILIES), default="chorded_cycle")
    profile_parser.add_argument("--size", type=int, default=16)
    profile_parser.add_argument("--repeats", type=int, default=1)
    profile_parser.add_argument("--out", type=Path, required=True)

    args = parser.parse_args()
    if args.cmd == "proof":
        proof(args.out)
    elif args.cmd == "direct":
        direct(args.out, args.repeats)
    elif args.cmd == "time":
        print(json.dumps(time_one(args.which, args.family, args.size, args.repeats), sort_keys=True))
    else:
        profile(args.which, args.family, args.size, args.repeats, args.out)


if __name__ == "__main__":
    main()
