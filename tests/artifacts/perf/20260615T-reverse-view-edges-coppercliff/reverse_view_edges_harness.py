#!/usr/bin/env python3
"""Baseline/profile/golden harness for br-r37-c1-04z53.9110."""

from __future__ import annotations

import argparse
import cProfile
import hashlib
import io
import json
import pstats
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


ARTIFACT_DIR = Path(__file__).resolve().parent
REPO_ROOT = ARTIFACT_DIR.parents[3]
REPO_PYTHON = REPO_ROOT / "python"

for path in (str(REPO_PYTHON), str(REPO_ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)

import franken_networkx as fnx  # noqa: E402
import networkx as nx  # noqa: E402


N = 1200
K = 8
P = 0.2
SEED = 3


def _git(*args: str) -> str:
    try:
        return subprocess.check_output(
            ["git", *args],
            cwd=REPO_ROOT,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception as exc:
        return f"<unavailable: {type(exc).__name__}: {exc}>"


def metadata() -> dict[str, Any]:
    return {
        "bead": "br-r37-c1-04z53.9110",
        "repo_root": str(REPO_ROOT),
        "head": _git("rev-parse", "HEAD"),
        "head_short": _git("log", "-1", "--oneline"),
        "python": sys.version,
        "franken_networkx_file": getattr(fnx, "__file__", None),
        "networkx_file": getattr(nx, "__file__", None),
        "networkx_version": getattr(nx, "__version__", None),
        "workload": "list(DG.reverse(copy=False).edges())",
        "graph": {
            "family": "DiGraph(watts_strogatz_graph(n, k, p, seed))",
            "n": N,
            "k": K,
            "p": P,
            "seed": SEED,
        },
    }


def build_graph(mod: Any, *, with_attrs: bool = False) -> Any:
    graph = mod.DiGraph(mod.watts_strogatz_graph(N, K, P, seed=SEED))
    if with_attrs:
        for idx, (u, v) in enumerate(list(graph.edges())):
            graph[u][v]["w"] = (idx % 17) - 3
            graph[u][v]["label"] = f"e{idx % 11}"
        for idx, node in enumerate(list(graph.nodes())[:16]):
            graph.nodes[node]["rank"] = idx
        graph.graph["case"] = "reverse-view-edges"
    return graph


def target(graph: Any) -> list[Any]:
    return list(graph.reverse(copy=False).edges())


def run_bench(mod_name: str, loops: int) -> None:
    mod = fnx if mod_name == "fnx" else nx
    graph = build_graph(mod)
    expected_edges = graph.number_of_edges()
    first = target(graph)
    if len(first) != expected_edges:
        raise AssertionError((len(first), expected_edges))

    start = time.perf_counter()
    digest = hashlib.sha256()
    total = 0
    for _ in range(loops):
        out = target(graph)
        total += len(out)
        digest.update(repr(out[:8]).encode())
        digest.update(repr(out[-8:]).encode())
    elapsed = time.perf_counter() - start
    result = {
        "mode": mod_name,
        "loops": loops,
        "edges_per_loop": expected_edges,
        "total_edges": total,
        "elapsed_seconds": elapsed,
        "seconds_per_loop": elapsed / loops,
        "digest": digest.hexdigest(),
        "metadata": metadata(),
    }
    print(json.dumps(result, sort_keys=True))


def run_profile(loops: int, output: Path) -> None:
    graph = build_graph(fnx)

    def profiled() -> None:
        for _ in range(loops):
            target(graph)

    profiler = cProfile.Profile()
    profiler.enable()
    profiled()
    profiler.disable()
    profiler.dump_stats(str(output.with_suffix(".prof")))

    stream = io.StringIO()
    stats = pstats.Stats(profiler, stream=stream).strip_dirs().sort_stats("cumulative")
    stats.print_stats(40)
    text = stream.getvalue()
    output.write_text(text, encoding="utf-8")
    print(text)


def canonical(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            repr(k): canonical(v)
            for k, v in sorted(value.items(), key=lambda item: repr(item[0]))
        }
    if isinstance(value, tuple):
        return {"tuple": [canonical(v) for v in value]}
    if isinstance(value, list):
        return [canonical(v) for v in value]
    if isinstance(value, set):
        return {"set": sorted(canonical(v) for v in value)}
    try:
        json.dumps(value)
        return value
    except TypeError:
        return {"repr": repr(value), "type": type(value).__name__}


def payload_bytes(value: Any) -> bytes:
    return json.dumps(
        canonical(value),
        sort_keys=True,
        separators=(",", ":"),
    ).encode()


def exception_surface(callable_obj: Any) -> dict[str, str]:
    try:
        callable_obj()
    except Exception as exc:
        return {"type": type(exc).__name__, "message": str(exc)}
    return {"type": "<no error>", "message": ""}


def golden_for(mod: Any) -> dict[str, Any]:
    graph = build_graph(mod, with_attrs=True)
    reverse = graph.reverse(copy=False)
    before = list(reverse.edges())

    live_new_edge = (N + 1, N)
    graph.add_edge(live_new_edge[0], live_new_edge[1], w=777, label="live")
    after = list(reverse.edges())

    frozen_errors = {
        "add_edge": exception_surface(lambda: reverse.add_edge(0, 1)),
        "remove_node": exception_surface(lambda: reverse.remove_node(0)),
        "clear": exception_surface(lambda: reverse.clear()),
    }

    return {
        "edge_order": before,
        "edge_data_true": list(reverse.edges(data=True)),
        "edge_data_attr_default": list(reverse.edges(data="w", default=-999)),
        "live_after_source_mutation": after,
        "live_new_edge_expected": (live_new_edge[1], live_new_edge[0]),
        "frozen_errors": frozen_errors,
        "node_count_after_live_mutation": graph.number_of_nodes(),
        "edge_count_after_live_mutation": graph.number_of_edges(),
    }


def run_golden(output: Path) -> None:
    fnx_payload = golden_for(fnx)
    nx_payload = golden_for(nx)

    cases = {}
    mismatches = []
    for name in fnx_payload:
        f_bytes = payload_bytes(fnx_payload[name])
        n_bytes = payload_bytes(nx_payload[name])
        match = f_bytes == n_bytes
        cases[name] = {
            "match": match,
            "fnx_sha256": hashlib.sha256(f_bytes).hexdigest(),
            "nx_sha256": hashlib.sha256(n_bytes).hexdigest(),
        }
        if not match:
            mismatches.append(name)

    fnx_all = payload_bytes(fnx_payload)
    nx_all = payload_bytes(nx_payload)
    bundle = {
        "metadata": metadata(),
        "cases": cases,
        "match": not mismatches and fnx_all == nx_all,
        "mismatches": mismatches,
        "fnx_sha256": hashlib.sha256(fnx_all).hexdigest(),
        "nx_sha256": hashlib.sha256(nx_all).hexdigest(),
        "samples": {
            "edge_order_first_8": fnx_payload["edge_order"][:8],
            "edge_order_last_8": fnx_payload["edge_order"][-8:],
            "live_after_source_mutation_last_8": fnx_payload[
                "live_after_source_mutation"
            ][-8:],
            "frozen_errors": fnx_payload["frozen_errors"],
        },
    }
    output.write_text(json.dumps(bundle, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (output.parent / "golden_reverse_edges.sha256").write_text(
        f"{bundle['fnx_sha256']}  golden_reverse_edges.fnx_payload\n"
        f"{bundle['nx_sha256']}  golden_reverse_edges.nx_payload\n",
        encoding="utf-8",
    )
    print(json.dumps(bundle, indent=2, sort_keys=True))


def main() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    for name in ("bench-fnx", "bench-nx"):
        sub = subparsers.add_parser(name)
        sub.add_argument("--loops", type=int, default=500)

    profile = subparsers.add_parser("profile-fnx")
    profile.add_argument("--loops", type=int, default=300)
    profile.add_argument(
        "--output",
        type=Path,
        default=ARTIFACT_DIR / "profile_fnx_reverse_edges.txt",
    )

    golden = subparsers.add_parser("golden")
    golden.add_argument(
        "--output",
        type=Path,
        default=ARTIFACT_DIR / "golden_reverse_edges.json",
    )

    meta = subparsers.add_parser("metadata")
    meta.add_argument(
        "--output",
        type=Path,
        default=ARTIFACT_DIR / "metadata.json",
    )

    args = parser.parse_args()
    if args.command == "bench-fnx":
        run_bench("fnx", args.loops)
    elif args.command == "bench-nx":
        run_bench("nx", args.loops)
    elif args.command == "profile-fnx":
        run_profile(args.loops, args.output)
    elif args.command == "golden":
        run_golden(args.output)
    elif args.command == "metadata":
        args.output.write_text(json.dumps(metadata(), indent=2, sort_keys=True) + "\n")
        print(args.output)


if __name__ == "__main__":
    main()
