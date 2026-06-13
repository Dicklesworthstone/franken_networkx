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


def _attrs(attrs):
    return [[str(key), _atom(value)] for key, value in sorted(dict(attrs).items())]


def _node_data_rows(rows):
    return [[_atom(node), _attrs(attrs)] for node, attrs in rows]


def _adjacency_rows(adjacency):
    return [
        [
            _atom(node),
            [[_atom(nbr), _attrs(attrs)] for nbr, attrs in nbrs.items()],
        ]
        for node, nbrs in adjacency.items()
    ]


def _digest(payload):
    text = json.dumps(payload, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def build_graph(lib, *, n=800):
    base = nx.connected_watts_strogatz_graph(n, 6, 0.3, seed=0)
    graph = lib.Graph()
    graph.add_nodes_from((node, {"value": node, "bucket": node % 7}) for node in base.nodes())
    graph.add_edges_from(base.edges())
    return graph


def run_operation(graph, operation):
    if operation == "nodes_data":
        return list(graph.nodes(data=True))
    if operation == "adjacency":
        return dict(graph.adjacency())
    raise ValueError(f"unknown operation: {operation}")


def serialize_result(operation, result):
    if operation == "nodes_data":
        return _node_data_rows(result)
    if operation == "adjacency":
        return _adjacency_rows(result)
    raise ValueError(f"unknown operation: {operation}")


def liveness_rows():
    graph = fnx.Graph()
    graph.add_node("a", color="red")
    view = graph.nodes(data=True)
    graph.add_node("b", color="blue")
    first = list(view)
    first[0][1]["seen"] = True
    after_attr_write = dict(graph.nodes(data=True))["a"].get("seen")
    adjacency = graph.adjacency()
    graph.add_edge("a", "b", weight=3)
    adjacency_after_edge = [[_atom(node), [_atom(nbr) for nbr in nbrs]] for node, nbrs in adjacency]
    return {
        "nodes_view_after_add": _node_data_rows(first),
        "node_attr_write_is_live": after_attr_write,
        "adjacency_after_edge": adjacency_after_edge,
    }


def command_golden(args):
    rows = []
    for operation in args.operations:
        fnx_result = run_operation(build_graph(fnx, n=args.nodes), operation)
        nx_result = run_operation(build_graph(nx, n=args.nodes), operation)
        rows.append(
            {
                "operation": operation,
                "fnx_sha256": _digest(serialize_result(operation, fnx_result)),
                "nx_sha256": _digest(serialize_result(operation, nx_result)),
                "fnx_rows": serialize_result(operation, fnx_result),
            }
        )
    payload = {
        "impl": "franken_networkx view materialization",
        "networkx_version": nx.__version__,
        "nodes": args.nodes,
        "rows": rows,
        "liveness": liveness_rows(),
    }
    text = json.dumps(payload, indent=2, ensure_ascii=True)
    args.output.write_text(text + "\n", encoding="utf-8")
    print(hashlib.sha256((text + "\n").encode("utf-8")).hexdigest())


def command_bench(args):
    lib = fnx if args.impl == "fnx" else nx
    graph = build_graph(lib, n=args.nodes)
    result = None
    timings = []
    for _ in range(args.loops):
        started = time.perf_counter()
        result = run_operation(graph, args.operation)
        timings.append(time.perf_counter() - started)
    payload = {
        "impl": args.impl,
        "operation": args.operation,
        "nodes": args.nodes,
        "loops": args.loops,
        "timings_s": timings,
        "best_s": min(timings),
        "mean_s": sum(timings) / len(timings),
        "sha256": _digest(serialize_result(args.operation, result)),
    }
    text = json.dumps(payload, sort_keys=True)
    if args.output is not None:
        args.output.write_text(text + "\n", encoding="utf-8")
    print(text)


def command_profile(args):
    lib = fnx if args.impl == "fnx" else nx
    graph = build_graph(lib, n=args.nodes)
    profiler = cProfile.Profile()
    profiler.enable()
    result = run_operation(graph, args.operation)
    profiler.disable()
    with args.output.open("w", encoding="utf-8") as handle:
        handle.write(
            f"impl={args.impl} operation={args.operation} nodes={args.nodes} "
            f"sha256={_digest(serialize_result(args.operation, result))}\n"
        )
        stats = pstats.Stats(profiler, stream=handle).sort_stats("cumulative")
        stats.print_stats(args.limit)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--nodes", type=int, default=800)
    subparsers = parser.add_subparsers(dest="command", required=True)

    golden = subparsers.add_parser("golden")
    golden.add_argument("--output", type=Path, required=True)
    golden.add_argument("--operations", nargs="*", default=["nodes_data", "adjacency"])
    golden.set_defaults(func=command_golden)

    bench = subparsers.add_parser("bench")
    bench.add_argument("--impl", choices=("fnx", "nx"), required=True)
    bench.add_argument("--operation", choices=("nodes_data", "adjacency"), required=True)
    bench.add_argument("--loops", type=int, default=20)
    bench.add_argument("--output", type=Path)
    bench.set_defaults(func=command_bench)

    profile = subparsers.add_parser("profile")
    profile.add_argument("--impl", choices=("fnx", "nx"), required=True)
    profile.add_argument("--operation", choices=("nodes_data", "adjacency"), required=True)
    profile.add_argument("--output", type=Path, required=True)
    profile.add_argument("--limit", type=int, default=40)
    profile.set_defaults(func=command_profile)

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main(sys.argv[1:])
