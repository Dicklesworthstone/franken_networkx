#!/usr/bin/env python3
"""Pass-1 benchmark/profile harness for max_weight_matching.

This file is an artifact, not product code. It intentionally avoids patching
franken_networkx and compares:
  * current FNX public path, which delegates through fnx->nx conversion
  * NetworkX direct path on a matching NetworkX graph
  * NetworkX's original blossom implementation over the FNX graph object
"""

from __future__ import annotations

import argparse
import cProfile
import hashlib
import io
import json
import pstats
import statistics
import sys
import time
from pathlib import Path
from typing import Any, Callable

import franken_networkx as fnx
import networkx as nx
import networkx.algorithms.matching as nx_matching


DEFAULT_OUTDIR = Path(__file__).resolve().parent


class CollidingNode:
    """Distinct nodes sharing one hash value for hash-collision parity cases."""

    __slots__ = ("label",)

    def __init__(self, label: str) -> None:
        self.label = label

    def __hash__(self) -> int:
        return 17

    def __eq__(self, other: object) -> bool:
        return isinstance(other, CollidingNode) and self.label == other.label

    def __repr__(self) -> str:
        return f"CollidingNode({self.label!r})"


def stable_edge_selector(i: int, j: int) -> int:
    return (
        (i * 1_103_515_245)
        ^ (j * 2_654_435_761)
        ^ ((i + 97) * (j + 193) * 97_531)
    ) & 0xFFFFFFFF


def weighted_edges(n: int, density_per_mille: int) -> list[tuple[int, int, int]]:
    edges: list[tuple[int, int, int]] = []
    for i in range(n):
        for j in range(i + 1, n):
            token = stable_edge_selector(i, j)
            if token % 1000 < density_per_mille:
                weight = ((i * 31 + j * 17 + token) % 23) + 1
                edges.append((i, j, weight))
    return edges


def build_pair(n: int, density_per_mille: int) -> tuple[fnx.Graph, nx.Graph]:
    edges = weighted_edges(n, density_per_mille)
    fg = fnx.Graph()
    ng = nx.Graph()
    fg.add_nodes_from(range(n))
    ng.add_nodes_from(range(n))
    fg.add_weighted_edges_from(edges)
    ng.add_weighted_edges_from(edges)
    return fg, ng


def canonical_node(node: Any) -> str:
    return f"{type(node).__module__}.{type(node).__qualname__}:{node!r}"


def canonical_matching(matching: set[tuple[Any, Any]]) -> list[list[str]]:
    return sorted(
        [[canonical_node(u), canonical_node(v)] for u, v in matching],
        key=lambda pair: (pair[0], pair[1]),
    )


def digest_payload(payload: Any) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def call_impl(
    impl: str,
    fg: fnx.Graph,
    ng: nx.Graph,
    *,
    maxcardinality: bool,
    weight: str | None,
) -> set[tuple[Any, Any]]:
    if impl == "fnx-current":
        return fnx.max_weight_matching(fg, maxcardinality=maxcardinality, weight=weight)
    if impl == "nx":
        return nx_matching.max_weight_matching(
            ng, maxcardinality=maxcardinality, weight=weight, backend="networkx"
        )
    if impl == "nx-orig-on-fnx":
        return nx_matching.max_weight_matching.orig_func(
            fg, maxcardinality=maxcardinality, weight=weight
        )
    raise ValueError(f"unknown impl: {impl}")


def measure(
    label: str,
    func: Callable[[], set[tuple[Any, Any]]],
    *,
    repeats: int,
    loops: int,
) -> dict[str, Any]:
    samples: list[float] = []
    result: set[tuple[Any, Any]] | None = None
    for _ in range(repeats):
        start = time.perf_counter()
        for _ in range(loops):
            result = func()
        elapsed = time.perf_counter() - start
        samples.append(elapsed / loops)
    return {
        "label": label,
        "loops_per_repeat": loops,
        "repeats": repeats,
        "samples_sec": samples,
        "min_sec": min(samples),
        "mean_sec": statistics.fmean(samples),
        "median_sec": statistics.median(samples),
        "stdev_sec": statistics.stdev(samples) if len(samples) > 1 else 0.0,
        "result_sha256": digest_payload(canonical_matching(result or set())),
        "result_size": len(result or set()),
    }


def direct_timing(args: argparse.Namespace) -> dict[str, Any]:
    fg, ng = build_pair(args.n, args.density)
    common = {
        "maxcardinality": args.maxcardinality,
        "weight": args.weight,
    }
    rows = [
        measure(
            "fnx-current",
            lambda: call_impl("fnx-current", fg, ng, **common),
            repeats=args.repeats,
            loops=args.loops,
        ),
        measure(
            "nx",
            lambda: call_impl("nx", fg, ng, **common),
            repeats=args.repeats,
            loops=args.loops,
        ),
        measure(
            "nx-orig-on-fnx",
            lambda: call_impl("nx-orig-on-fnx", fg, ng, **common),
            repeats=args.repeats,
            loops=args.loops,
        ),
    ]
    nx_mean = rows[1]["mean_sec"]
    for row in rows:
        row["ratio_vs_nx_mean"] = row["mean_sec"] / nx_mean if nx_mean else None
    payload = {
        "workload": {
            "n": args.n,
            "density_per_mille": args.density,
            "edges": len(weighted_edges(args.n, args.density)),
            "maxcardinality": args.maxcardinality,
            "weight": args.weight,
        },
        "versions": {
            "python": sys.version,
            "networkx": nx.__version__,
            "franken_networkx": getattr(fnx, "__version__", None),
        },
        "rows": rows,
    }
    if args.output:
        Path(args.output).write_text(json.dumps(payload, indent=2, sort_keys=True))
    return payload


def run_once(args: argparse.Namespace) -> None:
    fg, ng = build_pair(args.n, args.density)
    for _ in range(args.loops):
        result = call_impl(
            args.impl,
            fg,
            ng,
            maxcardinality=args.maxcardinality,
            weight=args.weight,
        )
    print(
        json.dumps(
            {
                "impl": args.impl,
                "n": args.n,
                "density_per_mille": args.density,
                "edges": len(weighted_edges(args.n, args.density)),
                "loops": args.loops,
                "result_size": len(result),
                "result_sha256": digest_payload(canonical_matching(result)),
            },
            sort_keys=True,
        )
    )


def golden_cases() -> list[tuple[str, list[Any], list[tuple[Any, Any, dict[str, Any]]], dict[str, Any]]]:
    tie_nodes = list("abcdef")
    tie_edges = [
        ("a", "b", {"weight": 5}),
        ("a", "c", {"weight": 5}),
        ("b", "d", {"weight": 5}),
        ("c", "d", {"weight": 5}),
        ("e", "f", {"weight": 5}),
    ]
    mixed_nodes = [0, "0", (0,), 1, "1", (1,), 2]
    mixed_edges = [
        (0, "0", {"weight": 4}),
        ("0", (0,), {}),
        ((0,), 1, {"weight": 4}),
        (1, "1", {"weight": 2}),
        ("1", (1,), {"weight": 7}),
        ((1,), 2, {}),
    ]
    collision_nodes = [CollidingNode(f"n{i}") for i in range(6)]
    collision_edges = [
        (collision_nodes[0], collision_nodes[1], {"weight": 3}),
        (collision_nodes[0], collision_nodes[2], {"weight": 3}),
        (collision_nodes[1], collision_nodes[3], {"weight": 8}),
        (collision_nodes[2], collision_nodes[4], {"weight": 8}),
        (collision_nodes[3], collision_nodes[5], {}),
        (collision_nodes[4], collision_nodes[5], {"weight": 1}),
    ]
    return [
        ("tie-heavy-weighted", tie_nodes, tie_edges, {"weight": "weight"}),
        ("tie-heavy-default-weight", tie_nodes, tie_edges, {"weight": None}),
        ("mixed-default-and-weighted", mixed_nodes, mixed_edges, {"weight": "weight"}),
        ("hash-collision-nodes", collision_nodes, collision_edges, {"weight": "weight"}),
    ]


def build_from_case(nodes: list[Any], edges: list[tuple[Any, Any, dict[str, Any]]]) -> tuple[fnx.Graph, nx.Graph]:
    fg = fnx.Graph()
    ng = nx.Graph()
    fg.add_nodes_from(nodes)
    ng.add_nodes_from(nodes)
    for u, v, attrs in edges:
        fg.add_edge(u, v, **attrs)
        ng.add_edge(u, v, **attrs)
    return fg, ng


def write_golden(args: argparse.Namespace) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    for case_name, nodes, edges, case_kwargs in golden_cases():
        fg, ng = build_from_case(nodes, edges)
        for maxcardinality in (False, True):
            weight = case_kwargs["weight"]
            nx_result = call_impl(
                "nx", fg, ng, maxcardinality=maxcardinality, weight=weight
            )
            fnx_result = call_impl(
                "fnx-current", fg, ng, maxcardinality=maxcardinality, weight=weight
            )
            direct_result = call_impl(
                "nx-orig-on-fnx", fg, ng, maxcardinality=maxcardinality, weight=weight
            )
            records.append(
                {
                    "case": case_name,
                    "maxcardinality": maxcardinality,
                    "weight": weight,
                    "fnx_equals_nx": fnx_result == nx_result,
                    "orig_on_fnx_equals_nx": direct_result == nx_result,
                    "nx": canonical_matching(nx_result),
                    "fnx_current": canonical_matching(fnx_result),
                    "nx_orig_on_fnx": canonical_matching(direct_result),
                }
            )
    payload = {
        "records": records,
        "all_fnx_current_equal": all(r["fnx_equals_nx"] for r in records),
        "all_orig_on_fnx_equal": all(r["orig_on_fnx_equals_nx"] for r in records),
    }
    payload["sha256"] = digest_payload(payload["records"])
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "golden_cases.json").write_text(json.dumps(payload, indent=2, sort_keys=True))
    (outdir / "golden_cases.sha256").write_text(f"{payload['sha256']}  golden_cases.json\n")
    return payload


def profile_impl(args: argparse.Namespace) -> dict[str, Any]:
    fg, ng = build_pair(args.n, args.density)
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    profile_path = outdir / f"profile_{args.impl}.prof"
    text_path = outdir / f"profile_{args.impl}.txt"
    prof = cProfile.Profile()

    def target() -> set[tuple[Any, Any]]:
        result: set[tuple[Any, Any]] = set()
        for _ in range(args.loops):
            result = call_impl(
                args.impl,
                fg,
                ng,
                maxcardinality=args.maxcardinality,
                weight=args.weight,
            )
        return result

    for _ in range(args.warmup):
        call_impl(
            args.impl,
            fg,
            ng,
            maxcardinality=args.maxcardinality,
            weight=args.weight,
        )

    prof.enable()
    result = target()
    prof.disable()
    prof.dump_stats(profile_path)
    stream = io.StringIO()
    stats = pstats.Stats(prof, stream=stream).strip_dirs().sort_stats("cumtime")
    stats.print_stats(args.profile_rows)
    text_path.write_text(stream.getvalue())
    payload = {
        "impl": args.impl,
        "n": args.n,
        "density_per_mille": args.density,
        "edges": len(weighted_edges(args.n, args.density)),
        "loops": args.loops,
        "warmup": args.warmup,
        "profile": str(profile_path),
        "text": str(text_path),
        "result_size": len(result),
        "result_sha256": digest_payload(canonical_matching(result)),
    }
    summary_path = outdir / f"profile_{args.impl}_summary.json"
    summary_path.write_text(json.dumps(payload, indent=2, sort_keys=True))
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="mode", required=True)

    def add_workload(p: argparse.ArgumentParser) -> None:
        p.add_argument("--n", type=int, default=180)
        p.add_argument("--density", type=int, default=160)
        p.add_argument("--loops", type=int, default=1)
        p.add_argument("--maxcardinality", action="store_true")
        p.add_argument("--weight", default="weight")

    p_direct = sub.add_parser("direct")
    add_workload(p_direct)
    p_direct.add_argument("--repeats", type=int, default=9)
    p_direct.add_argument("--output")

    p_once = sub.add_parser("run-once")
    add_workload(p_once)
    p_once.add_argument("--impl", choices=["fnx-current", "nx", "nx-orig-on-fnx"], required=True)

    p_golden = sub.add_parser("golden")
    p_golden.add_argument("--outdir", default=str(DEFAULT_OUTDIR))

    p_profile = sub.add_parser("profile")
    add_workload(p_profile)
    p_profile.add_argument("--impl", choices=["fnx-current", "nx", "nx-orig-on-fnx"], required=True)
    p_profile.add_argument("--outdir", default=str(DEFAULT_OUTDIR))
    p_profile.add_argument("--profile-rows", type=int, default=80)
    p_profile.add_argument("--warmup", type=int, default=1)

    args = parser.parse_args()
    if args.mode == "direct":
        print(json.dumps(direct_timing(args), indent=2, sort_keys=True))
    elif args.mode == "run-once":
        run_once(args)
    elif args.mode == "golden":
        print(json.dumps(write_golden(args), indent=2, sort_keys=True))
    elif args.mode == "profile":
        print(json.dumps(profile_impl(args), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
