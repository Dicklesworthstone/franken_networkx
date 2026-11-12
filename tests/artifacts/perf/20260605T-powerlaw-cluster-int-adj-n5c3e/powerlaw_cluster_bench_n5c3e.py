#!/usr/bin/env python3
"""Perf/parity harness for br-r37-c1-n5c3e."""

from __future__ import annotations

import argparse
import cProfile
import hashlib
import io
import json
import pstats
import statistics
import time

import franken_networkx as fnx
import networkx as nx


def graph_signature(graph):
    return {
        "nodes": list(graph.nodes()),
        "edges": [(u, v) for u, v in graph.edges()],
    }


def run_timing(label: str, module, n: int, m: int, p: float, seed: int, loops: int) -> dict:
    samples = []
    last_sig = None
    for _ in range(7):
        t0 = time.perf_counter()
        for i in range(loops):
            graph = module.powerlaw_cluster_graph(n, m, p, seed=seed + i)
            last_sig = graph_signature(graph)
        samples.append((time.perf_counter() - t0) / loops)
    return {
        "kind": "timing",
        "label": label,
        "n": n,
        "m": m,
        "p": p,
        "seed": seed,
        "loops": loops,
        "mean_sec": statistics.mean(samples),
        "median_sec": statistics.median(samples),
        "min_sec": min(samples),
        "samples_sec": samples,
        "last_digest": hashlib.sha256(
            json.dumps(last_sig, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest(),
    }


def run_golden() -> dict:
    cases = [
        (5, 5, 0.5, 1),
        (10, 2, 0.0, 42),
        (10, 2, 0.5, 42),
        (20, 3, 0.35, 7),
        (30, 4, 0.8, 13),
        (50, 5, 1.0, 99),
    ]
    rows = []
    for n, m, p, seed in cases:
        fg = fnx.powerlaw_cluster_graph(n, m, p, seed=seed)
        ng = nx.powerlaw_cluster_graph(n, m, p, seed=seed)
        fnx_sig = graph_signature(fg)
        nx_sig = graph_signature(ng)
        rows.append(
            {
                "n": n,
                "m": m,
                "p": p,
                "seed": seed,
                "fnx": fnx_sig,
                "networkx": nx_sig,
                "equal": fnx_sig == nx_sig,
            }
        )
    digest = hashlib.sha256(
        json.dumps(rows, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return {"kind": "golden", "rows": rows, "sha256": digest, "all_equal": all(r["equal"] for r in rows)}


def run_profile(n: int, m: int, p: float, seed: int, loops: int) -> dict:
    profile = cProfile.Profile()
    profile.enable()
    for i in range(loops):
        fnx.powerlaw_cluster_graph(n, m, p, seed=seed + i)
    profile.disable()
    buf = io.StringIO()
    pstats.Stats(profile, stream=buf).strip_dirs().sort_stats("cumtime").print_stats(25)
    return {"kind": "cprofile", "text": buf.getvalue()}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=1200)
    parser.add_argument("--m", type=int, default=4)
    parser.add_argument("--p", type=float, default=0.65)
    parser.add_argument("--seed", type=int, default=20260605)
    parser.add_argument("--loops", type=int, default=8)
    parser.add_argument("--profile-loops", type=int, default=5)
    args = parser.parse_args()

    print(json.dumps(run_timing("fnx_powerlaw_cluster_graph", fnx, args.n, args.m, args.p, args.seed, args.loops), sort_keys=True))
    print(json.dumps(run_timing("networkx_powerlaw_cluster_graph", nx, args.n, args.m, args.p, args.seed, args.loops), sort_keys=True))
    print(json.dumps(run_profile(args.n, args.m, args.p, args.seed, args.profile_loops), sort_keys=True))
    print(json.dumps(run_golden(), sort_keys=True))


if __name__ == "__main__":
    main()
