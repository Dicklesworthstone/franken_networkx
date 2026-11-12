#!/usr/bin/env python3
"""Focused proof and timing harness for br-r37-c1-04z53.81."""

from __future__ import annotations

import argparse
import cProfile
import hashlib
import json
import pstats
import statistics
import time
from io import StringIO
from typing import Any, Callable

import franken_networkx as fnx
import networkx as nx


def _stable(value: Any) -> Any:
    if isinstance(value, dict):
        return [[_stable(k), _stable(v)] for k, v in value.items()]
    if isinstance(value, set | frozenset):
        return sorted(_stable(item) for item in value)
    if isinstance(value, tuple):
        return [_stable(item) for item in value]
    if isinstance(value, list):
        return [_stable(item) for item in value]
    if isinstance(value, float):
        return repr(value)
    return value


def _digest(value: Any) -> str:
    raw = json.dumps(_stable(value), sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def _copy_to_fnx(graph: Any) -> Any:
    out = fnx.DiGraph() if graph.is_directed() else fnx.Graph()
    out.add_nodes_from(graph.nodes(data=True))
    out.add_edges_from(graph.edges(data=True))
    return out


def _target_graph(impl: str) -> Any:
    if impl == "fnx":
        return fnx.barabasi_albert_graph(1200, 4, seed=11)
    return nx.barabasi_albert_graph(1200, 4, seed=11)


def _stable_call(func: Callable[[], Any]) -> dict[str, Any]:
    try:
        value = func()
    except Exception as err:  # noqa: BLE001 - public exception contract artifact.
        return {"kind": "err", "message": str(err), "type": type(err).__name__}
    return {"kind": "ok", "value": _stable(value)}


def _proof_cases() -> list[tuple[str, Any, Any, Any]]:
    ba = nx.barabasi_albert_graph(1200, 4, seed=11)
    grid = nx.grid_2d_graph(6, 6)
    directed = nx.DiGraph()
    directed.add_edges_from([(0, 1), (0, 2), (1, 4), (2, 3), (3, 4)])
    string_tie = nx.Graph()
    string_tie.add_edges_from([("s", "a"), ("s", "b"), ("a", "t"), ("b", "t")])
    disconnected = nx.Graph()
    disconnected.add_edges_from([(0, 1)])
    disconnected.add_node(2)
    missing = nx.path_graph(4)
    return [
        ("ba_pair", ba, 0, 900),
        ("grid_tie_pair", grid, (0, 0), (5, 5)),
        ("directed_tie_pair", directed, 0, 4),
        ("string_tie_pair", string_tie, "s", "t"),
        ("source_equals_target", ba, 7, 7),
        ("no_path", disconnected, 0, 2),
        ("missing_source", missing, 99, 2),
        ("missing_target", missing, 0, 99),
    ]


def command_golden(_args: argparse.Namespace) -> int:
    rows = []
    for name, nx_graph, source, target in _proof_cases():
        fnx_graph = _copy_to_fnx(nx_graph)
        fnx_payload = _stable_call(lambda: fnx.shortest_path(fnx_graph, source, target))
        nx_payload = _stable_call(lambda: nx.shortest_path(nx_graph, source, target))
        rows.append(
            {
                "case": name,
                "fnx": fnx_payload,
                "match": fnx_payload == nx_payload,
                "nx": nx_payload,
            }
        )
    bundle = {
        "ordering_tie_rng_fp": {
            "floating_point": "not applicable; unweighted BFS path only",
            "ordering": "BA, grid, directed, and string tie cases compare exact returned path order",
            "rng": "BA graph construction uses deterministic seed before timing; shortest_path itself is deterministic",
            "tie_breaking": "bidirectional meet and path reconstruction are byte-compared against NetworkX",
        },
        "rows": rows,
    }
    bundle["bundle_sha256"] = _digest(bundle["rows"])
    print(json.dumps(bundle, sort_keys=True))
    return 0 if all(row["match"] for row in rows) else 1


def command_bench(args: argparse.Namespace) -> int:
    module = fnx if args.impl == "fnx" else nx
    graph = _target_graph(args.impl)
    samples = []
    digests = []
    for _ in range(args.repeats):
        start = time.perf_counter()
        value = None
        for _ in range(args.loops):
            value = module.shortest_path(graph, 0, 900)
        elapsed = time.perf_counter() - start
        samples.append(elapsed)
        digests.append(_digest(value))
    print(
        json.dumps(
            {
                "digest": _digest(digests),
                "impl": args.impl,
                "loops": args.loops,
                "max_s": max(samples),
                "mean_s": statistics.fmean(samples),
                "median_s": statistics.median(samples),
                "min_s": min(samples),
                "per_call_median_s": statistics.median(samples) / args.loops,
                "repeats": args.repeats,
                "samples_s": samples,
            },
            sort_keys=True,
        )
    )
    return 0


def command_profile(args: argparse.Namespace) -> int:
    graph = _target_graph("fnx")
    profiler = cProfile.Profile()
    profiler.enable()
    value = None
    for _ in range(args.loops):
        value = fnx.shortest_path(graph, 0, 900)
    profiler.disable()
    out = StringIO()
    pstats.Stats(profiler, stream=out).strip_dirs().sort_stats("cumtime").print_stats(args.limit)
    print("sha256=" + _digest(value) + "\n" + out.getvalue())
    return 0


def command_once(args: argparse.Namespace) -> int:
    module = fnx if args.impl == "fnx" else nx
    graph = _target_graph(args.impl)
    value = None
    for _ in range(args.loops):
        value = module.shortest_path(graph, 0, 900)
    print(json.dumps({"digest": _digest(value), "impl": args.impl, "path": _stable(value)}, sort_keys=True))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("golden").set_defaults(func=command_golden)

    bench = sub.add_parser("bench")
    bench.add_argument("--impl", choices=("fnx", "nx"), required=True)
    bench.add_argument("--loops", type=int, default=20000)
    bench.add_argument("--repeats", type=int, default=9)
    bench.set_defaults(func=command_bench)

    profile = sub.add_parser("profile")
    profile.add_argument("--loops", type=int, default=10000)
    profile.add_argument("--limit", type=int, default=40)
    profile.set_defaults(func=command_profile)

    once = sub.add_parser("once")
    once.add_argument("--impl", choices=("fnx", "nx"), required=True)
    once.add_argument("--loops", type=int, default=1)
    once.set_defaults(func=command_once)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
