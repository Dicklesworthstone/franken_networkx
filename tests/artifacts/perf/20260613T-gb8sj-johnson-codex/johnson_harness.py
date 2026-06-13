from __future__ import annotations

import argparse
import cProfile
import hashlib
import json
import pstats
import sys
import time
from pathlib import Path

import franken_networkx as fnx
import networkx as nx


ARTIFACT_DIR = Path(__file__).resolve().parent
GOLDEN_CASES = (
    "inner_order_repro",
    "int_tie_order",
    "directed_negative",
    "custom_weight",
    "callable_weight",
    "default_path",
    "ws60_weighted",
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


def _weighted_ws_graph(lib, n, k, p, seed):
    nx_graph = nx.watts_strogatz_graph(n, k, p, seed=seed)
    graph = lib.Graph()
    for node in nx_graph.nodes:
        graph.add_node(node)
    for u, v in nx_graph.edges:
        weight = ((u * 131 + v * 17 + seed) % 11) + 1
        graph.add_edge(u, v, weight=weight)
    return graph


def build_graph(lib, case):
    if case == "inner_order_repro":
        return _add_weighted_edges(
            lib.Graph(),
            [("a", "b", 1), ("b", "c", 2), ("c", "d", 1), ("a", "d", 5), ("b", "d", 3)],
        )
    if case == "int_tie_order":
        return _add_weighted_edges(
            lib.Graph(),
            [(0, 1, 1), (1, 2, 2), (2, 3, 3), (0, 3, 1)],
        )
    if case == "directed_negative":
        return _add_weighted_edges(
            lib.DiGraph(),
            [("a", "b", 1), ("b", "c", -2), ("a", "c", 4), ("c", "d", 3)],
        )
    if case == "custom_weight":
        return _add_weighted_edges(
            lib.Graph(),
            [("a", "b", 1), ("b", "c", 2), ("c", "d", 1)],
            weight_name="custom",
        )
    if case == "callable_weight":
        return _add_weighted_edges(
            lib.Graph(),
            [("a", "b", 1), ("b", "c", 2), ("c", "d", 1)],
        )
    if case == "default_path":
        return lib.path_graph(10) if lib is nx else fnx.path_graph(10)
    if case == "ws60_weighted":
        return _weighted_ws_graph(lib, 60, 8, 0.2, 61)
    if case == "ws150_weighted":
        return _weighted_ws_graph(lib, 150, 10, 0.2, 151)
    if case == "ws300_weighted":
        return _weighted_ws_graph(lib, 300, 10, 0.2, 313)
    if case == "ws500_weighted":
        return _weighted_ws_graph(lib, 500, 10, 0.2, 521)
    raise ValueError(f"unknown case: {case}")


def _weight(case):
    if case == "custom_weight":
        return "custom"
    if case == "callable_weight":
        return lambda _u, _v, data: data.get("weight", 1) * 2
    return "weight"


def run_paths(impl, case):
    lib = nx if impl == "nx" else fnx
    graph = build_graph(lib, case)
    weight = _weight(case)
    if impl == "fnx-apd":
        return dict(fnx.all_pairs_dijkstra_path(graph, weight=weight))
    return lib.johnson(graph, weight=weight)


def command_golden(args):
    cases = args.cases or GOLDEN_CASES
    rows = []
    for case in cases:
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
    weight = _weight(args.case)
    result = None
    timings = []
    for _ in range(args.loops):
        started = time.perf_counter()
        if args.impl == "fnx-apd":
            result = dict(fnx.all_pairs_dijkstra_path(graph, weight=weight))
        else:
            lib = fnx if args.impl == "fnx" else nx
            result = lib.johnson(graph, weight=weight)
        timings.append(time.perf_counter() - started)
    ordered_digest = _digest_ordered(result)
    output = {
        "impl": args.impl,
        "case": args.case,
        "loops": args.loops,
        "timings_s": timings,
        "best_s": min(timings),
        "mean_s": sum(timings) / len(timings),
        "sha256": ordered_digest,
    }
    text = json.dumps(output, sort_keys=True)
    if args.output is not None:
        args.output.write_text(text + "\n", encoding="utf-8")
    print(text)


def command_profile(args):
    graph_lib = nx if args.impl == "nx" else fnx
    graph = build_graph(graph_lib, args.case)
    weight = _weight(args.case)
    profiler = cProfile.Profile()
    profiler.enable()
    if args.impl == "fnx-apd":
        result = dict(fnx.all_pairs_dijkstra_path(graph, weight=weight))
    else:
        lib = fnx if args.impl == "fnx" else nx
        result = lib.johnson(graph, weight=weight)
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
    bench.add_argument("--impl", choices=("fnx", "nx", "fnx-apd"), required=True)
    bench.add_argument("--case", default="ws300_weighted")
    bench.add_argument("--loops", type=int, default=5)
    bench.add_argument("--output", type=Path)
    bench.set_defaults(func=command_bench)

    profile = subparsers.add_parser("profile")
    profile.add_argument("--impl", choices=("fnx", "nx", "fnx-apd"), required=True)
    profile.add_argument("--case", default="ws300_weighted")
    profile.add_argument("--output", type=Path, required=True)
    profile.add_argument("--limit", type=int, default=40)
    profile.set_defaults(func=command_profile)

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main(sys.argv[1:])
