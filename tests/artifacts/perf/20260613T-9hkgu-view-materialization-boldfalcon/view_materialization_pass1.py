#!/usr/bin/env python3
"""Benchmark and golden harness for br-r37-c1-9hkgu view materialization."""

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


def git_head() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=ARTIFACT_DIR.parents[3],
            text=True,
            stderr=subprocess.DEVNULL,
            timeout=5,
        ).strip()
    except Exception:
        return "unknown"


def make_graphs(n: int = 800, k: int = 6, p: float = 0.2, seed: int = 7):
    nx_graph = nx.watts_strogatz_graph(n, k, p, seed=seed)
    for node in nx_graph:
        if node % 10 == 0:
            nx_graph.nodes[node]["color"] = f"c{node % 7}"
    fnx_graph = fnx.Graph()
    fnx_graph.add_nodes_from(nx_graph.nodes(data=True))
    fnx_graph.add_edges_from(nx_graph.edges())
    return fnx_graph, nx_graph


def normalize_pairs(pairs):
    normalized = []
    for node, attrs in pairs:
        if isinstance(attrs, dict):
            normalized.append([node, sorted(attrs.items())])
        else:
            normalized.append([node, attrs])
    return normalized


def digest_payload(payload) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def exercise(impl: str, case: str, n: int, repeat: int):
    fnx_graph, nx_graph = make_graphs(n=n)
    graph = fnx_graph if impl == "fnx" else nx_graph
    digest = None
    started = time.perf_counter()
    for _ in range(repeat):
        if case == "nodes-data":
            result = list(graph.nodes(data=True))
            digest = digest_payload(normalize_pairs(result))
        elif case == "nodes-attr":
            result = list(graph.nodes(data="color", default="missing"))
            digest = digest_payload(normalize_pairs(result))
        elif case == "adjacency":
            result = dict(graph.adjacency())
            digest = digest_payload(
                [[node, list(row.keys())] for node, row in result.items()]
            )
        else:
            raise ValueError(f"unknown case: {case}")
    elapsed = time.perf_counter() - started
    return {
        "impl": impl,
        "case": case,
        "n": n,
        "repeat": repeat,
        "elapsed": elapsed,
        "per_iter": elapsed / repeat,
        "digest": digest,
    }


def golden_payload(n: int):
    fnx_graph, nx_graph = make_graphs(n=n)
    fnx_nodes_data = list(fnx_graph.nodes(data=True))
    nx_nodes_data = list(nx_graph.nodes(data=True))
    fnx_nodes_attr = list(fnx_graph.nodes(data="color", default="missing"))
    nx_nodes_attr = list(nx_graph.nodes(data="color", default="missing"))
    fnx_adj = dict(fnx_graph.adjacency())
    nx_adj = dict(nx_graph.adjacency())

    yielded = list(fnx_graph.nodes(data=True))
    yielded[0][1]["mutated_through_view"] = 17
    mutation_visible = fnx_graph.nodes[yielded[0][0]].get("mutated_through_view")

    payload = {
        "git_head": git_head(),
        "n": n,
        "fnx_nodes_data": normalize_pairs(fnx_nodes_data[:25]),
        "nx_nodes_data": normalize_pairs(nx_nodes_data[:25]),
        "nodes_data_equal": normalize_pairs(fnx_nodes_data)
        == normalize_pairs(nx_nodes_data),
        "fnx_nodes_attr": normalize_pairs(fnx_nodes_attr[:25]),
        "nx_nodes_attr": normalize_pairs(nx_nodes_attr[:25]),
        "nodes_attr_equal": normalize_pairs(fnx_nodes_attr)
        == normalize_pairs(nx_nodes_attr),
        "fnx_adj_keys": [[node, list(row.keys())] for node, row in list(fnx_adj.items())[:25]],
        "nx_adj_keys": [[node, list(row.keys())] for node, row in list(nx_adj.items())[:25]],
        "adj_keys_equal": [[node, list(row.keys())] for node, row in fnx_adj.items()]
        == [[node, list(row.keys())] for node, row in nx_adj.items()],
        "mutation_visible": mutation_visible,
    }
    payload["digest"] = digest_payload(payload)
    return payload


def write_json(path: Path, payload) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def cmd_golden(args) -> None:
    payload = golden_payload(args.n)
    out = ARTIFACT_DIR / f"{args.prefix}_golden.json"
    write_json(out, payload)
    sha = hashlib.sha256(out.read_bytes()).hexdigest()
    (ARTIFACT_DIR / f"{args.prefix}_golden.sha256").write_text(
        f"{sha}  {out.name}\n", encoding="utf-8"
    )
    print(json.dumps({"path": str(out), "sha256": sha, "digest": payload["digest"]}))


def cmd_loop(args) -> None:
    samples = [exercise(args.impl, args.case, args.n, args.repeat) for _ in range(args.samples)]
    per_iter = [sample["per_iter"] for sample in samples]
    payload = {
        "git_head": git_head(),
        "impl": args.impl,
        "case": args.case,
        "n": args.n,
        "repeat": args.repeat,
        "samples": args.samples,
        "mean": statistics.mean(per_iter),
        "median": statistics.median(per_iter),
        "min": min(per_iter),
        "max": max(per_iter),
        "digest": samples[-1]["digest"],
        "raw": samples,
    }
    if args.output:
        write_json(Path(args.output), payload)
    print(json.dumps(payload, sort_keys=True))


def cmd_profile(args) -> None:
    profile = cProfile.Profile()
    profile.enable()
    exercise(args.impl, args.case, args.n, args.repeat)
    profile.disable()
    with Path(args.output).open("w", encoding="utf-8") as handle:
        stats = pstats.Stats(profile, stream=handle).sort_stats("cumulative")
        stats.print_stats(args.limit)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)

    golden = sub.add_parser("golden")
    golden.add_argument("--prefix", required=True)
    golden.add_argument("--n", type=int, default=800)
    golden.set_defaults(func=cmd_golden)

    loop = sub.add_parser("loop")
    loop.add_argument("--impl", choices=["fnx", "nx"], required=True)
    loop.add_argument("--case", choices=["nodes-data", "nodes-attr", "adjacency"], required=True)
    loop.add_argument("--n", type=int, default=800)
    loop.add_argument("--repeat", type=int, default=2000)
    loop.add_argument("--samples", type=int, default=7)
    loop.add_argument("--output")
    loop.set_defaults(func=cmd_loop)

    profile = sub.add_parser("profile")
    profile.add_argument("--impl", choices=["fnx", "nx"], required=True)
    profile.add_argument("--case", choices=["nodes-data", "nodes-attr", "adjacency"], required=True)
    profile.add_argument("--n", type=int, default=800)
    profile.add_argument("--repeat", type=int, default=1000)
    profile.add_argument("--output", required=True)
    profile.add_argument("--limit", type=int, default=40)
    profile.set_defaults(func=cmd_profile)

    args = parser.parse_args(argv)
    args.func(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
