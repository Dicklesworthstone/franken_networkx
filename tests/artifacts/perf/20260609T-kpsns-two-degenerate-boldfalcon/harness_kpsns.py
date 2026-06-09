#!/usr/bin/env python3
"""Proof and timing harness for br-r37-c1-kpsns k_components residual."""

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


class FlowProbe(Exception):
    """Raised when NetworkX reaches its flow-based residual path."""


def genuine_nx_k_components(graph, flow_func=None):
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


def result_digest(result) -> str:
    return hashlib.sha256(
        json.dumps(canonical(result), sort_keys=True).encode()
    ).hexdigest()


def graph_digest(graph) -> str:
    payload = {
        "nodes": sorted(repr(node) for node in graph.nodes()),
        "edges": sorted((repr(u), repr(v)) for u, v in graph.edges()),
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def chorded_cycle(lib, n: int):
    graph = lib.cycle_graph(n)
    for node in range(0, n, 4):
        graph.add_edge(node, (node + 2) % n)
    return graph


def square_with_diagonal(lib, _size: int):
    graph = lib.Graph()
    graph.add_edges_from([(0, 1), (1, 2), (2, 3), (3, 0), (0, 2)])
    return graph


def circular_ladder(lib, n: int):
    return lib.circular_ladder_graph(n)


FAMILIES: dict[str, Callable[[object, int], object]] = {
    "chorded_cycle": chorded_cycle,
    "square_with_diagonal": square_with_diagonal,
    "circular_ladder": circular_ladder,
}

PROOF_CASES = [
    ("square_with_diagonal", 0),
    ("chorded_cycle", 12),
    ("chorded_cycle", 16),
    ("circular_ladder", 6),
]


def make_graph(which: str, family: str, size: int):
    lib = fnx if which == "fnx" else nx
    return FAMILIES[family](lib, size)


def flow_probe(which: str, family: str, size: int) -> dict[str, object]:
    def fail_flow(*_args, **_kwargs):
        raise FlowProbe("flow called")

    graph = make_graph(which, family, size)
    func = fnx.k_components if which == "fnx" else genuine_nx_k_components
    try:
        func(graph, flow_func=fail_flow)
    except FlowProbe as exc:
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
            "fnx": flow_probe("fnx", family, size),
            "nx": flow_probe("nx", family, size),
        },
    }


def proof(out: Path) -> None:
    rows = [case_record(family, size) for family, size in PROOF_CASES]
    payload = {
        "bead": "br-r37-c1-kpsns",
        "python": sys.executable,
        "fnx_file": fnx.__file__,
        "nx_file": nx.__file__,
        "nx_version": nx.__version__,
        "genuine_networkx": "nx.k_components.orig_func",
        "cases": rows,
        "all_match": all(row["match"] for row in rows),
        "isomorphism": {
            "ordering_preserved": "golden records k order and component order",
            "tie_breaking_unchanged": "accepted cases have one maximal k=2 component per connected component; rejected 3-core graph delegates",
            "floating_point": "N/A: output is integer node-set structure",
            "rng": "N/A: graph builders are deterministic",
            "custom_flow": "flow_func sentinel must still be observed by FNX and genuine NX",
        },
    }
    text = json.dumps(payload, sort_keys=True, indent=2)
    out.write_text(text + "\n", encoding="utf-8")
    print(hashlib.sha256((text + "\n").encode()).hexdigest())
    if not payload["all_match"]:
        raise SystemExit("proof mismatch")


def time_one(which: str, family: str, size: int, repeats: int) -> dict[str, object]:
    graph = make_graph(which, family, size)
    func = fnx.k_components if which == "fnx" else genuine_nx_k_components
    result = None
    start = time.perf_counter()
    for _ in range(repeats):
        result = func(graph)
    seconds = time.perf_counter() - start
    return {
        "which": which,
        "family": family,
        "size": size,
        "nodes": graph.number_of_nodes(),
        "edges": graph.number_of_edges(),
        "repeats": repeats,
        "seconds": seconds,
        "seconds_per_call": seconds / repeats,
        "result_sha256": result_digest(result),
    }


def direct(out: Path, samples: int) -> None:
    rows = []
    for family, size in [("chorded_cycle", 12), ("chorded_cycle", 16)]:
        fnx_samples = []
        nx_samples = []
        last = {}
        for _ in range(samples):
            fnx_record = time_one("fnx", family, size, 1)
            nx_record = time_one("nx", family, size, 1)
            fnx_samples.append(fnx_record["seconds_per_call"])
            nx_samples.append(nx_record["seconds_per_call"])
            last = fnx_record
        rows.append(
            {
                "family": family,
                "size": size,
                "nodes": last["nodes"],
                "edges": last["edges"],
                "result_sha256": last["result_sha256"],
                "fnx_samples": fnx_samples,
                "nx_samples": nx_samples,
                "fnx_mean": statistics.mean(fnx_samples),
                "nx_mean": statistics.mean(nx_samples),
                "fnx_median": statistics.median(fnx_samples),
                "nx_median": statistics.median(nx_samples),
            }
        )
    out.write_text(json.dumps({"rows": rows}, sort_keys=True, indent=2) + "\n")


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
            handle.write(f"profile which={which} family={family} size={size}\n")
            handle.write(f"fnx_file={fnx.__file__}\n")
            handle.write(f"nx_file={nx.__file__}\n")
            stats.stream = handle
            stats.print_stats(80)


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)

    proof_parser = sub.add_parser("proof")
    proof_parser.add_argument("--out", type=Path, required=True)

    direct_parser = sub.add_parser("direct")
    direct_parser.add_argument("--out", type=Path, required=True)
    direct_parser.add_argument("--samples", type=int, default=3)

    time_parser = sub.add_parser("time")
    time_parser.add_argument("--which", choices=["fnx", "nx"], required=True)
    time_parser.add_argument("--family", choices=sorted(FAMILIES), required=True)
    time_parser.add_argument("--size", type=int, required=True)
    time_parser.add_argument("--repeats", type=int, default=1)

    profile_parser = sub.add_parser("profile")
    profile_parser.add_argument("--which", choices=["fnx", "nx"], required=True)
    profile_parser.add_argument("--family", choices=sorted(FAMILIES), required=True)
    profile_parser.add_argument("--size", type=int, required=True)
    profile_parser.add_argument("--repeats", type=int, default=1)
    profile_parser.add_argument("--out", type=Path, required=True)

    args = parser.parse_args()
    if args.cmd == "proof":
        proof(args.out)
    elif args.cmd == "direct":
        direct(args.out, args.samples)
    elif args.cmd == "time":
        print(
            json.dumps(
                time_one(args.which, args.family, args.size, args.repeats),
                sort_keys=True,
            )
        )
    else:
        profile(args.which, args.family, args.size, args.repeats, args.out)


if __name__ == "__main__":
    main()
