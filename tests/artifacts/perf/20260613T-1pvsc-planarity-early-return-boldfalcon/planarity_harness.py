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


def _digest(payload):
    text = json.dumps(payload, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _base_graph(case):
    if case == "grid":
        graph = nx.convert_node_labels_to_integers(
            nx.grid_2d_graph(30, 20),
            ordering="sorted",
        )
    elif case == "random":
        graph = nx.gnp_random_graph(600, 0.01, seed=0)
    else:
        raise ValueError(f"unknown case: {case}")
    for node in graph:
        graph.nodes[node]["bucket"] = node % 11
    for idx, (u, v) in enumerate(graph.edges()):
        graph.edges[u, v]["weight"] = idx % 13
    graph.graph["case"] = case
    return graph


def build_graph(lib, case):
    base = _base_graph(case)
    graph = lib.Graph()
    graph.graph.update(base.graph)
    graph.add_nodes_from((node, dict(attrs)) for node, attrs in base.nodes(data=True))
    graph.add_edges_from((u, v, dict(attrs)) for u, v, attrs in base.edges(data=True))
    return graph


def _embedding_rows(embedding):
    if embedding is None:
        return None
    rows = []
    for node in embedding:
        rows.append(
            [
                _atom(node),
                [_atom(nbr) for nbr in embedding.neighbors_cw_order(node)],
            ]
        )
    return rows


def serialize_result(result):
    is_planar, certificate = result
    return {
        "is_planar": bool(is_planar),
        "certificate_type": type(certificate).__name__ if certificate is not None else None,
        "embedding": _embedding_rows(certificate),
    }


def run_operation(graph, counterexample):
    return fnx.check_planarity(graph, counterexample=counterexample)


def command_golden(args):
    rows = []
    for case in args.cases:
        fnx_result = serialize_result(run_operation(build_graph(fnx, case), args.counterexample))
        nx_result = serialize_result(nx.check_planarity(build_graph(nx, case), counterexample=args.counterexample))
        rows.append(
            {
                "case": case,
                "fnx_sha256": _digest(fnx_result),
                "nx_sha256": _digest(nx_result),
                "fnx_result": fnx_result,
            }
        )
    payload = {
        "impl": "franken_networkx check_planarity",
        "networkx_version": nx.__version__,
        "counterexample": args.counterexample,
        "rows": rows,
    }
    text = json.dumps(payload, indent=2, ensure_ascii=True)
    args.output.write_text(text + "\n", encoding="utf-8")
    print(hashlib.sha256((text + "\n").encode("utf-8")).hexdigest())


def command_bench(args):
    graph = build_graph(fnx, args.case)
    result = None
    timings = []
    for _ in range(args.loops):
        started = time.perf_counter()
        result = run_operation(graph, args.counterexample)
        timings.append(time.perf_counter() - started)
    payload = {
        "case": args.case,
        "counterexample": args.counterexample,
        "loops": args.loops,
        "timings_s": timings,
        "best_s": min(timings),
        "mean_s": sum(timings) / len(timings),
        "sha256": _digest(serialize_result(result)),
    }
    text = json.dumps(payload, sort_keys=True)
    args.output.write_text(text + "\n", encoding="utf-8")
    print(text)


def command_profile(args):
    graph = build_graph(fnx, args.case)
    profiler = cProfile.Profile()
    profiler.enable()
    result = run_operation(graph, args.counterexample)
    profiler.disable()
    with args.output.open("w", encoding="utf-8") as handle:
        handle.write(
            f"case={args.case} counterexample={args.counterexample} "
            f"sha256={_digest(serialize_result(result))}\n"
        )
        stats = pstats.Stats(profiler, stream=handle).sort_stats("cumulative")
        stats.print_stats(args.limit)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--counterexample", action="store_true")
    subparsers = parser.add_subparsers(dest="command", required=True)

    golden = subparsers.add_parser("golden")
    golden.add_argument("--output", type=Path, required=True)
    golden.add_argument("--cases", nargs="*", default=["grid", "random"])
    golden.set_defaults(func=command_golden)

    bench = subparsers.add_parser("bench")
    bench.add_argument("--case", choices=("grid", "random"), required=True)
    bench.add_argument("--loops", type=int, default=20)
    bench.add_argument("--output", type=Path, required=True)
    bench.set_defaults(func=command_bench)

    profile = subparsers.add_parser("profile")
    profile.add_argument("--case", choices=("grid", "random"), required=True)
    profile.add_argument("--output", type=Path, required=True)
    profile.add_argument("--limit", type=int, default=60)
    profile.set_defaults(func=command_profile)

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main(sys.argv[1:])
