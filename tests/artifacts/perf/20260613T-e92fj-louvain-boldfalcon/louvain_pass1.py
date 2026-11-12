#!/usr/bin/env python3
"""Pass-1 Louvain benchmark and golden harness for br-r37-c1-e92fj."""

from __future__ import annotations

import argparse
import cProfile
import hashlib
import json
import pstats
import statistics
import subprocess
import sys
import time
from pathlib import Path

import franken_networkx as fnx
import networkx as nx


ARTIFACT_DIR = Path(__file__).resolve().parent
DEFAULT_SEED = 12345


def _git_head() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=ARTIFACT_DIR.parents[3],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        return "unknown"


def _weighted_copy(graph: nx.Graph) -> nx.Graph:
    weighted = graph.copy()
    for index, (left, right) in enumerate(weighted.edges()):
        weighted[left][right]["weight"] = 1.0 + ((index * 7) % 11) / 10.0
    return weighted


def make_case(name: str) -> tuple[nx.Graph, str, float, float, int | None]:
    if name == "karate":
        return nx.karate_club_graph(), "weight", 1.0, 1.0e-7, None
    if name == "ws150":
        return nx.watts_strogatz_graph(150, 6, 0.20, seed=20260613), "weight", 1.0, 1.0e-7, None
    if name == "ws300":
        return nx.watts_strogatz_graph(300, 6, 0.20, seed=20260613), "weight", 1.0, 1.0e-7, None
    if name == "ba300":
        return nx.barabasi_albert_graph(300, 4, seed=20260613), "weight", 1.0, 1.0e-7, None
    if name == "ws150_weighted":
        return _weighted_copy(nx.watts_strogatz_graph(150, 6, 0.20, seed=20260613)), "weight", 1.0, 1.0e-7, None
    if name == "ws150_resolution":
        return nx.watts_strogatz_graph(150, 6, 0.20, seed=20260613), "weight", 0.75, 1.0e-7, None
    raise ValueError(f"unknown case: {name}")


def fnx_graph_from(nx_graph: nx.Graph) -> fnx.Graph:
    graph = fnx.Graph()
    graph.add_nodes_from(nx_graph.nodes(data=True))
    graph.add_edges_from(nx_graph.edges(data=True))
    return graph


def normalized(partition) -> list[list[int]]:
    normalized_partition = []
    for community in partition:
        normalized_partition.append(sorted(int(node) for node in community))
    return normalized_partition


def run_variant(variant: str, case_name: str, seed: int = DEFAULT_SEED):
    nx_graph, weight, resolution, threshold, max_level = make_case(case_name)
    fnx_graph = fnx_graph_from(nx_graph)
    if variant == "nx_original":
        return nx.community.louvain_communities(
            nx_graph,
            weight=weight,
            resolution=resolution,
            threshold=threshold,
            max_level=max_level,
            seed=seed,
        )
    if variant == "nx_parity":
        parity_graph = fnx._networkx_graph_for_parity(fnx_graph)
        return nx.community.louvain_communities(
            parity_graph,
            weight=weight,
            resolution=resolution,
            threshold=threshold,
            max_level=max_level,
            seed=seed,
        )
    if variant == "fnx_public":
        return fnx.community.louvain_communities(
            fnx_graph,
            weight=weight,
            resolution=resolution,
            threshold=threshold,
            max_level=max_level,
            seed=seed,
        )
    if variant == "fnx_raw":
        return fnx._raw_louvain_communities(
            fnx_graph,
            weight,
            resolution,
            threshold,
            max_level,
            seed,
        )
    raise ValueError(f"unknown variant: {variant}")


def golden(seed: int = DEFAULT_SEED) -> dict:
    cases = []
    for case_name in [
        "karate",
        "ws150",
        "ws300",
        "ba300",
        "ws150_weighted",
        "ws150_resolution",
    ]:
        public = normalized(run_variant("fnx_public", case_name, seed))
        nx_original = normalized(run_variant("nx_original", case_name, seed))
        nx_parity = normalized(run_variant("nx_parity", case_name, seed))
        raw = normalized(run_variant("fnx_raw", case_name, seed))
        cases.append(
            {
                "case": case_name,
                "seed": seed,
                "fnx_public": public,
                "nx_original": nx_original,
                "nx_parity": nx_parity,
                "fnx_raw": raw,
                "fnx_public_equals_nx_parity": public == nx_parity,
                "fnx_public_equals_nx_original": public == nx_original,
                "fnx_raw_equals_nx_parity": raw == nx_parity,
                "fnx_raw_equals_public": raw == public,
            }
        )
    payload = {
        "meta": {
            "bead": "br-r37-c1-e92fj",
            "git_head": _git_head(),
            "python": sys.version,
            "franken_networkx_file": fnx.__file__,
            "networkx_version": nx.__version__,
            "ordering": "partition order preserved; community members sorted only for digest comparability",
            "rng": "seeded NetworkX py_random_state integer seed reused for all variants",
            "floating_point": "no direct FP output; Louvain modularity decisions affect discrete partition",
        },
        "cases": cases,
    }
    return payload


def write_golden() -> dict:
    payload = golden()
    golden_path = ARTIFACT_DIR / "baseline_golden.json"
    sha_path = ARTIFACT_DIR / "baseline_golden.sha256"
    golden_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    digest = hashlib.sha256(golden_path.read_bytes()).hexdigest()
    sha_path.write_text(f"{digest}  {golden_path.name}\n")
    summary = {"sha256": digest, "path": str(golden_path), "cases": payload["cases"]}
    print(json.dumps(summary, sort_keys=True))
    return summary


def loop(
    variant: str,
    case_name: str,
    repeat: int,
    warmup: int,
    seed: int,
    output: Path | None = None,
) -> dict:
    for _ in range(warmup):
        normalized(run_variant(variant, case_name, seed))
    times = []
    last = None
    for _ in range(repeat):
        start = time.perf_counter()
        last = normalized(run_variant(variant, case_name, seed))
        times.append(time.perf_counter() - start)
    payload = {
        "variant": variant,
        "case": case_name,
        "repeat": repeat,
        "warmup": warmup,
        "seed": seed,
        "times": times,
        "mean": statistics.fmean(times),
        "median": statistics.median(times),
        "min": min(times),
        "max": max(times),
        "partition_digest": hashlib.sha256(
            json.dumps(last, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest(),
    }
    encoded = json.dumps(payload, sort_keys=True)
    if output is not None:
        output.write_text(encoded + "\n")
    print(encoded)
    return payload


def profile(variant: str, case_name: str, repeat: int, seed: int, output: Path) -> None:
    profiler = cProfile.Profile()

    def target() -> None:
        for _ in range(repeat):
            normalized(run_variant(variant, case_name, seed))

    profiler.enable()
    target()
    profiler.disable()
    with output.open("w") as handle:
        stats = pstats.Stats(profiler, stream=handle).strip_dirs().sort_stats("cumtime")
        stats.print_stats(40)


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("golden")

    loop_parser = sub.add_parser("loop")
    loop_parser.add_argument("variant", choices=["fnx_public", "fnx_raw", "nx_original", "nx_parity"])
    loop_parser.add_argument("case")
    loop_parser.add_argument("--repeat", type=int, default=20)
    loop_parser.add_argument("--warmup", type=int, default=3)
    loop_parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    loop_parser.add_argument("--output", type=Path)

    profile_parser = sub.add_parser("profile")
    profile_parser.add_argument("variant", choices=["fnx_public", "fnx_raw", "nx_original", "nx_parity"])
    profile_parser.add_argument("case")
    profile_parser.add_argument("--repeat", type=int, default=5)
    profile_parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    profile_parser.add_argument("--output", type=Path, required=True)

    args = parser.parse_args()
    if args.command == "golden":
        write_golden()
    elif args.command == "loop":
        loop(args.variant, args.case, args.repeat, args.warmup, args.seed, args.output)
    elif args.command == "profile":
        profile(args.variant, args.case, args.repeat, args.seed, args.output)


if __name__ == "__main__":
    main()
