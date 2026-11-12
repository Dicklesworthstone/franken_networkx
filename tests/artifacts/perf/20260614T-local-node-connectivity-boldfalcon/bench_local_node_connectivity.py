#!/usr/bin/env python3
"""Focused proof and benchmark harness for approximation.local_node_connectivity."""

from __future__ import annotations

import argparse
import cProfile
import hashlib
import json
import os
import pstats
import random
import statistics
import sys
import time
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
os.environ.setdefault("NETWORKX_AUTOMATIC_BACKENDS", "")

import networkx as nx
import networkx.algorithms.approximation as nxa

import franken_networkx as fnx
import franken_networkx.approximation as fa

try:
    nx.config.backend_priority = []
except Exception:
    pass


TARGET_N = 1500
TARGET_P = 0.01
TARGET_SEED = 3
TARGET_SOURCE = 0
TARGET_TARGET = TARGET_N // 2


def _fnx_from_nx(graph):
    out = fnx.Graph()
    out.add_nodes_from(graph.nodes())
    out.add_edges_from(graph.edges())
    return out


def _target_graphs():
    nx_graph = nx.gnp_random_graph(TARGET_N, TARGET_P, seed=TARGET_SEED)
    return nx_graph, _fnx_from_nx(nx_graph)


def _call(which, graph, source, target, cutoff=None):
    if which == "fnx":
        return fa.local_node_connectivity(graph, source, target, cutoff)
    if which == "nx":
        return nxa.local_node_connectivity(graph, source, target, cutoff)
    raise ValueError(which)


def _capture(fn):
    try:
        return {"kind": "ok", "value": fn()}
    except Exception as exc:
        return {"kind": "err", "type": type(exc).__name__, "message": str(exc)}


def _golden_rows():
    rows = []
    rng = random.Random(1729)
    for seed in range(12):
        for n, p in ((50, 0.10), (80, 0.07), (120, 0.05), (180, 0.035)):
            nx_graph = nx.gnp_random_graph(n, p, seed=seed)
            fnx_graph = _fnx_from_nx(nx_graph)
            nodes = list(nx_graph)
            for _ in range(6):
                source = rng.choice(nodes)
                target = rng.choice(nodes)
                if source == target:
                    continue
                for cutoff in (None, 1, 2, True, -1):
                    rows.append(
                        {
                            "case": f"gnp:{n}:{p}:{seed}:{source}:{target}:{cutoff!r}",
                            "nx": _capture(
                                lambda nx_graph=nx_graph, source=source, target=target, cutoff=cutoff: nxa.local_node_connectivity(
                                    nx_graph, source, target, cutoff
                                )
                            ),
                            "fnx": _capture(
                                lambda fnx_graph=fnx_graph, source=source, target=target, cutoff=cutoff: fa.local_node_connectivity(
                                    fnx_graph, source, target, cutoff
                                )
                            ),
                        }
                    )

    oct_nx = nx.octahedral_graph()
    oct_fnx = _fnx_from_nx(oct_nx)
    for source, target, cutoff in ((0, 5, None), (0, 1, None), (0, 5, 2)):
        rows.append(
            {
                "case": f"octahedral:{source}:{target}:{cutoff!r}",
                "nx": _capture(lambda source=source, target=target, cutoff=cutoff: nxa.local_node_connectivity(oct_nx, source, target, cutoff)),
                "fnx": _capture(lambda source=source, target=target, cutoff=cutoff: fa.local_node_connectivity(oct_fnx, source, target, cutoff)),
            }
        )

    path_nx = nx.path_graph(4)
    path_fnx = _fnx_from_nx(path_nx)
    error_cases = (
        ("same-node", 0, 0, None),
        ("missing-source", 99, 2, None),
        ("missing-target", 1, 99, None),
        ("float-cutoff", 0, 3, 1.5),
    )
    for name, source, target, cutoff in error_cases:
        rows.append(
            {
                "case": name,
                "nx": _capture(lambda source=source, target=target, cutoff=cutoff: nxa.local_node_connectivity(path_nx, source, target, cutoff)),
                "fnx": _capture(lambda source=source, target=target, cutoff=cutoff: fa.local_node_connectivity(path_fnx, source, target, cutoff)),
            }
        )
    return rows


def cmd_golden(args):
    rows = _golden_rows()
    for row in rows:
        row["match"] = row["nx"] == row["fnx"]
    payload = {
        "ordering_tie_rng_fp": {
            "ordering": "BFS neighbor order is compared through exact local connectivity return/error rows over nx-built graphs.",
            "tie_breaking": "White-Newman level-alternating bidirectional BFS is exercised across random and octahedral tie cases.",
            "rng": "Random graphs and pair sampling use fixed seeds before timing; the algorithm itself is deterministic.",
            "floating_point": "N/A: integer connectivity counts only.",
        },
        "rows": rows,
    }
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    payload["bundle_sha256"] = hashlib.sha256(blob).hexdigest()
    payload["all_match"] = all(row["match"] for row in rows)
    print(json.dumps(payload, sort_keys=True, indent=2))
    return 0 if payload["all_match"] else 1


def _run_loop(which, loops):
    nx_graph, fnx_graph = _target_graphs()
    graph = fnx_graph if which == "fnx" else nx_graph
    total = 0
    for _ in range(loops):
        total += _call(which, graph, TARGET_SOURCE, TARGET_TARGET)
    return total


def _percentile(values, pct):
    ordered = sorted(values)
    idx = min(len(ordered) - 1, int(round((len(ordered) - 1) * pct)))
    return ordered[idx]


def cmd_bench(args):
    samples = []
    checksum = 0
    for _ in range(args.repeats):
        start = time.perf_counter()
        checksum += _run_loop(args.which, args.loops)
        samples.append(time.perf_counter() - start)
    payload = {
        "which": args.which,
        "loops": args.loops,
        "repeats": args.repeats,
        "checksum": checksum,
        "seconds": samples,
        "median": statistics.median(samples),
        "mean": statistics.mean(samples),
        "p95": _percentile(samples, 0.95),
        "per_call_median_us": statistics.median(samples) * 1_000_000 / args.loops,
        "target": {
            "n": TARGET_N,
            "p": TARGET_P,
            "seed": TARGET_SEED,
            "source": TARGET_SOURCE,
            "target": TARGET_TARGET,
        },
    }
    print(json.dumps(payload, sort_keys=True, indent=2))
    return 0


def cmd_loop(args):
    print(_run_loop(args.which, args.loops))
    return 0


def cmd_profile(args):
    profiler = cProfile.Profile()
    profiler.enable()
    checksum = _run_loop(args.which, args.loops)
    profiler.disable()
    print(f"checksum={checksum}")
    stats = pstats.Stats(profiler).sort_stats("cumtime")
    stats.print_stats(args.limit)
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)

    golden = sub.add_parser("golden")
    golden.set_defaults(func=cmd_golden)

    bench = sub.add_parser("bench")
    bench.add_argument("--which", choices=("fnx", "nx"), required=True)
    bench.add_argument("--loops", type=int, default=2000)
    bench.add_argument("--repeats", type=int, default=11)
    bench.set_defaults(func=cmd_bench)

    loop = sub.add_parser("loop")
    loop.add_argument("--which", choices=("fnx", "nx"), required=True)
    loop.add_argument("--loops", type=int, default=2000)
    loop.set_defaults(func=cmd_loop)

    profile = sub.add_parser("profile")
    profile.add_argument("--which", choices=("fnx", "nx"), required=True)
    profile.add_argument("--loops", type=int, default=4000)
    profile.add_argument("--limit", type=int, default=35)
    profile.set_defaults(func=cmd_profile)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
