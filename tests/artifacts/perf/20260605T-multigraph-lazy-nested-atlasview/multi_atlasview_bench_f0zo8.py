#!/usr/bin/env python3
"""Perf and parity harness for br-r37-c1-f0zo8.

Targets the nested adjacency path for MultiGraph/MultiDiGraph:
bare ``G[u]`` and point ``G[u][v]`` on high-degree parallel-edge nodes.
"""

from __future__ import annotations

import argparse
import cProfile
import hashlib
import json
import pstats
import sys
import time
from collections.abc import Iterable, Mapping
from io import StringIO


def _import_lib(name: str):
    if name == "fnx":
        import franken_networkx as lib
    elif name == "nx":
        import networkx as lib
    else:
        raise ValueError(name)
    return lib


def _build_graph(lib, graph_kind: str, neighbors: int, keys: int):
    cls = lib.MultiDiGraph if graph_kind == "multidigraph" else lib.MultiGraph
    graph = cls()
    for node in range(neighbors + 1):
        graph.add_node(node)
    for neighbor in range(1, neighbors + 1):
        for key in range(keys):
            graph.add_edge(0, neighbor, key=key, weight=neighbor * 10 + key)
    return graph


def _small_graph(lib, graph_kind: str):
    cls = lib.MultiDiGraph if graph_kind == "multidigraph" else lib.MultiGraph
    graph = cls()
    graph.add_node(0, color="root")
    graph.add_edge(0, 1, key="a", weight=1)
    graph.add_edge(0, 1, key="b", weight=2)
    graph.add_edge(0, 2, key=0)
    graph.add_edge(2, 0, key="reverse", label="r")
    return graph


def _stable_obj(value):
    if isinstance(value, Mapping):
        return [[_stable_obj(k), _stable_obj(v)] for k, v in value.items()]
    if isinstance(value, Iterable) and not isinstance(value, (str, bytes, bytearray)):
        return [_stable_obj(v) for v in value]
    if isinstance(value, (list, tuple)):
        return [_stable_obj(v) for v in value]
    if isinstance(value, set):
        return sorted(_stable_obj(v) for v in value)
    return value


def semantic_record(lib_name: str, graph_kind: str):
    lib = _import_lib(lib_name)
    graph = _small_graph(lib, graph_kind)
    view = graph[0]
    keydict = view[1]
    first_attrs = keydict["a"]
    first_attrs["weight"] = 99
    graph.add_edge(0, 3, key="late", marker="live")
    copied = view.copy()
    copied[1]["a"]["weight"] = -1
    try:
        _ = view[404]
    except Exception as exc:  # noqa: BLE001 - record observable exception contract.
        missing = {
            "type": type(exc).__name__,
            "args": _stable_obj(exc.args),
            "str": str(exc),
        }
    else:
        missing = None
    return {
        "lib": lib_name,
        "graph_kind": graph_kind,
        "view_type": type(view).__name__,
        "keydict_type": type(keydict).__name__,
        "view_repr_prefix": repr(view).split("(", 1)[0],
        "view_str": str(view),
        "neighbors": list(view),
        "items": _stable_obj(view.items()),
        "values": _stable_obj(view.values()),
        "keys_for_1": list(keydict),
        "key_items_for_1": _stable_obj(keydict.items()),
        "live_late_visible": 3 in view,
        "live_mutation_weight": graph[0][1]["a"]["weight"],
        "copy_isolated_weight": graph[0][1]["a"]["weight"],
        "copy_snapshot": _stable_obj(copied),
        "missing": missing,
    }


def command_golden(args: argparse.Namespace) -> int:
    records = []
    for graph_kind in ("multigraph", "multidigraph"):
        for lib_name in ("fnx", "nx"):
            records.append(semantic_record(lib_name, graph_kind))
    payload = json.dumps(records, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    print(json.dumps({"kind": "golden_digest", "sha256": digest}, sort_keys=True))
    for record in records:
        print(json.dumps(record, sort_keys=True, default=str))
    fnx_records = [r for r in records if r["lib"] == "fnx"]
    nx_records = [r for r in records if r["lib"] == "nx"]
    comparable = [
        {
            key: value
            for key, value in record.items()
            if key not in {"lib", "view_type", "keydict_type", "view_repr_prefix"}
        }
        for record in fnx_records
    ]
    nx_comparable = [
        {
            key: value
            for key, value in record.items()
            if key not in {"lib", "view_type", "keydict_type", "view_repr_prefix"}
        }
        for record in nx_records
    ]
    if comparable != nx_comparable:
        print("FNX/NX semantic mismatch", file=sys.stderr)
        return 1
    return 0


def _bench_case(lib_name: str, graph_kind: str, operation: str, loops: int, neighbors: int, keys: int):
    lib = _import_lib(lib_name)
    graph = _build_graph(lib, graph_kind, neighbors, keys)
    target = neighbors
    sink = 0
    start = time.perf_counter()
    if operation == "bare":
        for _ in range(loops):
            view = graph[0]
            sink ^= id(view) & 1
    elif operation == "point":
        for _ in range(loops):
            keydict = graph[0][target]
            sink += len(keydict)
    else:
        raise ValueError(operation)
    elapsed = time.perf_counter() - start
    return {
        "lib": lib_name,
        "graph_kind": graph_kind,
        "operation": operation,
        "loops": loops,
        "neighbors": neighbors,
        "keys": keys,
        "elapsed_s": elapsed,
        "mean_s": elapsed / loops,
        "sink": sink,
    }


def command_bench(args: argparse.Namespace) -> int:
    record = _bench_case(
        args.lib,
        args.graph_kind,
        args.operation,
        args.loops,
        args.neighbors,
        args.keys,
    )
    print(json.dumps(record, sort_keys=True))
    return 0


def command_sweep(args: argparse.Namespace) -> int:
    for graph_kind in ("multigraph", "multidigraph"):
        for operation in ("bare", "point"):
            for lib_name in ("fnx", "nx"):
                record = _bench_case(
                    lib_name,
                    graph_kind,
                    operation,
                    args.loops,
                    args.neighbors,
                    args.keys,
                )
                print(json.dumps(record, sort_keys=True))
    return 0


def command_profile(args: argparse.Namespace) -> int:
    profiler = cProfile.Profile()
    profiler.enable()
    record = _bench_case(
        args.lib,
        args.graph_kind,
        args.operation,
        args.loops,
        args.neighbors,
        args.keys,
    )
    profiler.disable()
    print(json.dumps(record, sort_keys=True))
    stream = StringIO()
    pstats.Stats(profiler, stream=stream).strip_dirs().sort_stats("cumulative").print_stats(40)
    print(stream.getvalue(), end="")
    return 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    golden = sub.add_parser("golden")
    golden.set_defaults(func=command_golden)

    bench = sub.add_parser("bench")
    bench.add_argument("--lib", choices=("fnx", "nx"), required=True)
    bench.add_argument("--graph-kind", choices=("multigraph", "multidigraph"), required=True)
    bench.add_argument("--operation", choices=("bare", "point"), required=True)
    bench.add_argument("--loops", type=int, default=100)
    bench.add_argument("--neighbors", type=int, default=2000)
    bench.add_argument("--keys", type=int, default=3)
    bench.set_defaults(func=command_bench)

    sweep = sub.add_parser("sweep")
    sweep.add_argument("--loops", type=int, default=100)
    sweep.add_argument("--neighbors", type=int, default=2000)
    sweep.add_argument("--keys", type=int, default=3)
    sweep.set_defaults(func=command_sweep)

    profile = sub.add_parser("profile")
    profile.add_argument("--lib", choices=("fnx", "nx"), required=True)
    profile.add_argument("--graph-kind", choices=("multigraph", "multidigraph"), required=True)
    profile.add_argument("--operation", choices=("bare", "point"), required=True)
    profile.add_argument("--loops", type=int, default=100)
    profile.add_argument("--neighbors", type=int, default=2000)
    profile.add_argument("--keys", type=int, default=3)
    profile.set_defaults(func=command_profile)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
