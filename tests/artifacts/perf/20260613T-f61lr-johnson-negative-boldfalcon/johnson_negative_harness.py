from __future__ import annotations

import argparse
import cProfile
import hashlib
import importlib.util
import json
import os
import pstats
import sys
import time
from pathlib import Path

_EXTENSION_PATH = os.environ.get("FNX_EXTENSION_PATH")
if _EXTENSION_PATH:
    _SPEC = importlib.util.spec_from_file_location("franken_networkx._fnx", _EXTENSION_PATH)
    if _SPEC is None or _SPEC.loader is None:
        raise RuntimeError(f"cannot load FNX extension from {_EXTENSION_PATH}")
    _MODULE = importlib.util.module_from_spec(_SPEC)
    sys.modules["franken_networkx._fnx"] = _MODULE
    _SPEC.loader.exec_module(_MODULE)

import franken_networkx as fnx
import networkx as nx


GOLDEN_CASES = (
    "negative_small",
    "negative_tie_order",
    "negative_dag_80",
)


def _atom(value):
    if isinstance(value, bool):
        return ["bool", value]
    if isinstance(value, int):
        return ["int", value]
    if isinstance(value, float):
        return ["float", repr(value)]
    if isinstance(value, str):
        return ["str", value]
    if value is None:
        return ["none", None]
    return ["repr", repr(value)]


def _ordered_paths(paths):
    return [
        [
            _atom(source),
            [[_atom(target), [_atom(node) for node in path]] for target, path in inner.items()],
        ]
        for source, inner in paths.items()
    ]


def _digest_ordered(paths):
    payload = json.dumps(_ordered_paths(paths), separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _add_weighted_edges(graph, edges, weight_name="weight"):
    for u, v, weight in edges:
        graph.add_edge(u, v, **{weight_name: weight})
    return graph


def _negative_dag(lib, n, width, seed):
    graph = lib.DiGraph()
    nodes = [f"n{i:04d}" for i in range(n)]
    graph.add_nodes_from(nodes)
    for i, source in enumerate(nodes):
        for step in range(1, width + 1):
            target_index = i + step
            if target_index >= n:
                break
            # A directed acyclic graph can carry negative edges without negative
            # cycles. Keep integer weights so type parity is observable.
            weight = ((i * 37 + step * 19 + seed) % 17) - 5
            graph.add_edge(source, nodes[target_index], weight=weight)
    return graph


def build_graph(lib, case):
    if case == "negative_small":
        return _add_weighted_edges(
            lib.DiGraph(),
            [
                ("a", "b", 1),
                ("a", "c", 4),
                ("b", "c", -2),
                ("b", "d", 3),
                ("c", "d", 2),
                ("a", "d", 10),
            ],
        )
    if case == "negative_tie_order":
        return _add_weighted_edges(
            lib.DiGraph(),
            [
                ("s", "a", 2),
                ("s", "b", 1),
                ("b", "a", 1),
                ("a", "t", -1),
                ("b", "t", 0),
                ("s", "t", 5),
            ],
        )
    if case == "negative_dag_80":
        return _negative_dag(lib, 80, 5, 80)
    if case == "negative_dag_220":
        return _negative_dag(lib, 220, 8, 220)
    if case == "negative_dag_360":
        return _negative_dag(lib, 360, 8, 360)
    raise ValueError(f"unknown case: {case}")


def run_paths(impl, case):
    lib = nx if impl == "nx" else fnx
    graph = build_graph(lib, case)
    return lib.johnson(graph, weight="weight")


def command_golden(args):
    rows = []
    for case in args.cases or GOLDEN_CASES:
        fnx_paths = run_paths("fnx", case)
        nx_paths = run_paths("nx", case)
        if fnx_paths != nx_paths:
            raise AssertionError(f"{case}: path mapping differs")
        if _ordered_paths(fnx_paths) != _ordered_paths(nx_paths):
            raise AssertionError(f"{case}: ordered mapping differs")
        rows.append(
            {
                "case": case,
                "outer_order": [_atom(node) for node in fnx_paths.keys()],
                "sha256": _digest_ordered(fnx_paths),
                "ordered_paths": _ordered_paths(fnx_paths),
            }
        )
    output = {
        "impl": "franken_networkx.johnson",
        "networkx_version": nx.__version__,
        "cases": rows,
    }
    text = json.dumps(output, indent=2, sort_keys=False, ensure_ascii=True)
    args.output.write_text(text + "\n", encoding="utf-8")
    print(hashlib.sha256((text + "\n").encode("utf-8")).hexdigest())


def command_bench(args):
    graph_lib = nx if args.impl == "nx" else fnx
    graph = build_graph(graph_lib, args.case)
    result = None
    timings = []
    for _ in range(args.loops):
        started = time.perf_counter()
        lib = fnx if args.impl == "fnx" else nx
        result = lib.johnson(graph, weight="weight")
        timings.append(time.perf_counter() - started)
    output = {
        "impl": args.impl,
        "case": args.case,
        "loops": args.loops,
        "timings_s": timings,
        "best_s": min(timings),
        "mean_s": sum(timings) / len(timings),
        "sha256": _digest_ordered(result),
    }
    text = json.dumps(output, sort_keys=True)
    if args.output is not None:
        args.output.write_text(text + "\n", encoding="utf-8")
    print(text)


def command_profile(args):
    graph_lib = nx if args.impl == "nx" else fnx
    graph = build_graph(graph_lib, args.case)
    profiler = cProfile.Profile()
    profiler.enable()
    result = (fnx if args.impl == "fnx" else nx).johnson(graph, weight="weight")
    profiler.disable()
    with args.output.open("w", encoding="utf-8") as handle:
        handle.write(f"impl={args.impl} case={args.case} sha256={_digest_ordered(result)}\n")
        stats = pstats.Stats(profiler, stream=handle).sort_stats("cumulative")
        stats.print_stats(args.limit)


def main(argv=None):
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    golden = subparsers.add_parser("golden")
    golden.add_argument("--output", type=Path, required=True)
    golden.add_argument("--cases", nargs="*")
    golden.set_defaults(func=command_golden)

    bench = subparsers.add_parser("bench")
    bench.add_argument("--impl", choices=("fnx", "nx"), required=True)
    bench.add_argument("--case", default="negative_dag_220")
    bench.add_argument("--loops", type=int, default=3)
    bench.add_argument("--output", type=Path)
    bench.set_defaults(func=command_bench)

    profile = subparsers.add_parser("profile")
    profile.add_argument("--impl", choices=("fnx", "nx"), required=True)
    profile.add_argument("--case", default="negative_dag_220")
    profile.add_argument("--output", type=Path, required=True)
    profile.add_argument("--limit", type=int, default=50)
    profile.set_defaults(func=command_profile)

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main(sys.argv[1:])
