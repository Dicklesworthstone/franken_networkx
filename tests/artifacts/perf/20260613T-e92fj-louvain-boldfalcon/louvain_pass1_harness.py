#!/usr/bin/env python3
"""Pass-1 Louvain parity and benchmark harness for br-r37-c1-e92fj."""

from __future__ import annotations

import argparse
import cProfile
import hashlib
import json
import pstats
import sys
import time
from pathlib import Path
from typing import Any, Callable

import networkx as nx

import franken_networkx as fnx
from franken_networkx import _fnx


ARTIFACT_DIR = Path(__file__).resolve().parent
DEFAULT_GOLDEN = ARTIFACT_DIR / "louvain_pass1_golden.json"
DEFAULT_SHA = ARTIFACT_DIR / "louvain_pass1_golden.sha256"


def _build_nx_graph(nodes: list[Any], edges: list[tuple[Any, Any]]) -> nx.Graph:
    graph = nx.Graph()
    graph.add_nodes_from(nodes)
    graph.add_edges_from(edges)
    return graph


def _build_fnx_graph(nodes: list[Any], edges: list[tuple[Any, Any]]) -> fnx.Graph:
    graph = fnx.Graph()
    graph.add_nodes_from(nodes)
    graph.add_edges_from(edges)
    return graph


def _graph_pair(source: nx.Graph) -> tuple[nx.Graph, fnx.Graph]:
    nodes = list(source.nodes)
    edges = list(source.edges)
    return _build_nx_graph(nodes, edges), _build_fnx_graph(nodes, edges)


def _case_path_12() -> tuple[nx.Graph, fnx.Graph]:
    return _graph_pair(nx.path_graph(12))


def _case_cycle_18() -> tuple[nx.Graph, fnx.Graph]:
    return _graph_pair(nx.cycle_graph(18))


def _case_barbell_4_2() -> tuple[nx.Graph, fnx.Graph]:
    return _graph_pair(nx.barbell_graph(4, 2))


def _case_karate() -> tuple[nx.Graph, fnx.Graph]:
    return _graph_pair(nx.karate_club_graph())


def _case_ws_150() -> tuple[nx.Graph, fnx.Graph]:
    return _graph_pair(nx.watts_strogatz_graph(150, 6, 0.12, seed=17))


def _case_ws_300() -> tuple[nx.Graph, fnx.Graph]:
    return _graph_pair(nx.watts_strogatz_graph(300, 6, 0.10, seed=23))


CASES: dict[str, Callable[[], tuple[nx.Graph, fnx.Graph]]] = {
    "path_12": _case_path_12,
    "cycle_18": _case_cycle_18,
    "barbell_4_2": _case_barbell_4_2,
    "karate": _case_karate,
    "ws_150": _case_ws_150,
    "ws_300": _case_ws_300,
}

SEEDS = (0, 1, 7)


def _normalize_partition(partition: Any) -> list[list[Any]]:
    return [sorted(list(community)) for community in partition]


def _run_variant(
    variant: str,
    nx_graph: nx.Graph,
    fnx_graph: fnx.Graph,
    *,
    seed: int,
) -> list[list[Any]]:
    if variant == "nx":
        return _normalize_partition(
            nx.community.louvain_communities(nx_graph, seed=seed)
        )
    if variant == "public":
        return _normalize_partition(
            fnx.community.louvain_communities(fnx_graph, seed=seed)
        )
    if variant == "raw":
        return _normalize_partition(_fnx.louvain_communities(fnx_graph, seed=seed))
    raise ValueError(f"unknown variant: {variant}")


def _timed_call(
    variant: str,
    nx_graph: nx.Graph,
    fnx_graph: fnx.Graph,
    *,
    seed: int,
) -> tuple[list[list[Any]], float]:
    start = time.perf_counter()
    result = _run_variant(variant, nx_graph, fnx_graph, seed=seed)
    return result, time.perf_counter() - start


def _case_record(case_name: str, seed: int) -> dict[str, Any]:
    nx_graph, fnx_graph = CASES[case_name]()
    expected, nx_seconds = _timed_call("nx", nx_graph, fnx_graph, seed=seed)
    public, public_seconds = _timed_call("public", nx_graph, fnx_graph, seed=seed)

    raw_error = None
    try:
        raw, raw_seconds = _timed_call("raw", nx_graph, fnx_graph, seed=seed)
    except Exception as exc:  # pragma: no cover - artifact harness records failures
        raw = None
        raw_seconds = None
        raw_error = f"{type(exc).__name__}: {exc}"

    return {
        "case": case_name,
        "seed": seed,
        "nodes": nx_graph.number_of_nodes(),
        "edges": nx_graph.number_of_edges(),
        "nx": expected,
        "public": public,
        "raw": raw,
        "parity": {
            "public_matches_nx": public == expected,
            "raw_matches_nx": raw == expected,
            "raw_error": raw_error,
        },
        "seconds": {
            "nx": nx_seconds,
            "public": public_seconds,
            "raw": raw_seconds,
        },
    }


def _stable_json_bytes(payload: Any) -> bytes:
    return json.dumps(payload, indent=2, sort_keys=True).encode("utf-8") + b"\n"


def write_golden(path: Path, sha_path: Path) -> int:
    records = [_case_record(case, seed) for case in CASES for seed in SEEDS]
    payload = {
        "bead": "br-r37-c1-e92fj",
        "mission": "pass1_louvain_baseline_raw_kernel_parity_gate",
        "python": sys.version.split()[0],
        "networkx": nx.__version__,
        "franken_networkx": str(Path(fnx.__file__).resolve()),
        "raw_available": hasattr(_fnx, "louvain_communities"),
        "semantics": {
            "graphs": "simple undirected unweighted",
            "partition_encoding": (
                "list order preserved from implementation; each community sorted "
                "for stable JSON because NetworkX returns sets"
            ),
            "rng_seeds": list(SEEDS),
            "floating_point": "default NetworkX/Rust f64 Louvain modularity path",
        },
        "records": records,
    }
    payload["summary"] = {
        "record_count": len(records),
        "public_failures": sum(
            not record["parity"]["public_matches_nx"] for record in records
        ),
        "raw_failures": sum(
            not record["parity"]["raw_matches_nx"] for record in records
        ),
    }
    data = _stable_json_bytes(payload)
    path.write_bytes(data)
    digest = hashlib.sha256(data).hexdigest()
    sha_path.write_text(f"{digest}  {path.name}\n", encoding="utf-8")
    print(json.dumps({"golden": str(path), "sha256": digest, **payload["summary"]}))
    return 0 if payload["summary"]["public_failures"] == 0 else 1


def bench(variant: str, case_name: str, seed: int, loops: int) -> int:
    nx_graph, fnx_graph = CASES[case_name]()
    start = time.perf_counter()
    last = None
    for _ in range(loops):
        last = _run_variant(variant, nx_graph, fnx_graph, seed=seed)
    elapsed = time.perf_counter() - start
    print(
        json.dumps(
            {
                "variant": variant,
                "case": case_name,
                "seed": seed,
                "loops": loops,
                "elapsed_seconds": elapsed,
                "per_loop_seconds": elapsed / loops,
                "communities": len(last or ()),
            },
            sort_keys=True,
        )
    )
    return 0


def profile(variant: str, case_name: str, seed: int, loops: int, output: Path) -> int:
    def run() -> None:
        bench(variant, case_name, seed, loops)

    profiler = cProfile.Profile()
    profiler.enable()
    run()
    profiler.disable()
    with output.open("w", encoding="utf-8") as fh:
        stats = pstats.Stats(profiler, stream=fh)
        stats.strip_dirs().sort_stats("cumtime").print_stats(40)
    print(json.dumps({"profile": str(output), "variant": variant, "case": case_name}))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="mode", required=True)

    golden_parser = subparsers.add_parser("golden")
    golden_parser.add_argument("--output", type=Path, default=DEFAULT_GOLDEN)
    golden_parser.add_argument("--sha-output", type=Path, default=DEFAULT_SHA)

    bench_parser = subparsers.add_parser("bench")
    bench_parser.add_argument("--variant", choices=("nx", "public", "raw"), required=True)
    bench_parser.add_argument("--case", choices=tuple(CASES), default="ws_150")
    bench_parser.add_argument("--seed", type=int, default=1)
    bench_parser.add_argument("--loops", type=int, default=5)

    profile_parser = subparsers.add_parser("profile")
    profile_parser.add_argument("--variant", choices=("nx", "public", "raw"), required=True)
    profile_parser.add_argument("--case", choices=tuple(CASES), default="ws_150")
    profile_parser.add_argument("--seed", type=int, default=1)
    profile_parser.add_argument("--loops", type=int, default=5)
    profile_parser.add_argument("--output", type=Path, required=True)

    args = parser.parse_args()
    if args.mode == "golden":
        return write_golden(args.output, args.sha_output)
    if args.mode == "bench":
        return bench(args.variant, args.case, args.seed, args.loops)
    if args.mode == "profile":
        return profile(args.variant, args.case, args.seed, args.loops, args.output)
    raise AssertionError(args.mode)


if __name__ == "__main__":
    raise SystemExit(main())
