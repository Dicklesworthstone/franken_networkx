#!/usr/bin/env python3
from __future__ import annotations

import argparse
import cProfile
import gc
import hashlib
import io
import json
import pstats
import statistics
import time
from typing import Any

import franken_networkx as fnx
import networkx as nx


def _make_graph(lib: Any, n: int, m: int, seed: int) -> Any:
    graph = lib.barabasi_albert_graph(n, m, seed=seed)
    return graph


def _old_equivalent(graph: Any, u: int, v: int) -> set[Any]:
    graph = fnx._coerce_arg_to_fnx_graph(graph)
    if graph.is_directed():
        raise fnx.NetworkXNotImplemented("not implemented for directed type")
    if u not in graph:
        raise fnx.NetworkXError("u is not in the graph.")
    if v not in graph:
        raise fnx.NetworkXError("v is not in the graph.")
    raw_nbrs = fnx._raw_neighbors_dispatch(graph)
    if raw_nbrs is not None:
        return set(raw_nbrs(graph, u)) & set(raw_nbrs(graph, v)) - {u, v}
    return set(graph.adj[u]) & set(graph.adj[v]) - {u, v}


def _call(mode: str, fnx_graph: Any, nx_graph: Any, u: int, v: int) -> set[Any]:
    if mode == "old":
        return _old_equivalent(fnx_graph, u, v)
    if mode == "new":
        return set(fnx.common_neighbors(fnx_graph, u, v))
    if mode == "nx":
        return set(nx.common_neighbors(nx_graph, u, v))
    raise ValueError(mode)


def _norm(values: set[Any]) -> list[str]:
    return sorted(repr(value) for value in values)


def _sha(values: set[Any]) -> str:
    return hashlib.sha256(
        json.dumps(_norm(values), separators=(",", ":")).encode()
    ).hexdigest()


def golden(args: argparse.Namespace) -> None:
    cases = [
        ("ba1200", 1200, 4, 17, 0, 10),
        ("ba1200_empty", 1200, 4, 17, 2, 1199),
        ("ba200", 200, 3, 23, 0, 7),
    ]
    rows = []
    for name, n, m, seed, u, v in cases:
        fnx_graph = fnx.Graph(_make_graph(nx, n, m, seed))
        nx_graph = _make_graph(nx, n, m, seed)
        old = _call("old", fnx_graph, nx_graph, u, v)
        new = _call("new", fnx_graph, nx_graph, u, v)
        ref = _call("nx", fnx_graph, nx_graph, u, v)
        rows.append(
            {
                "case": name,
                "match": old == new == ref,
                "old_sha256": _sha(old),
                "new_sha256": _sha(new),
                "nx_sha256": _sha(ref),
                "len": len(new),
            }
        )
    payload = {
        "all_match": all(row["match"] for row in rows),
        "cases": rows,
        "isomorphism": {
            "ordering": "N/A: public output is a set",
            "tie_breaking": "N/A",
            "floating_point": "N/A",
            "rng": "N/A",
            "missing_node_errors": "covered by existing focused pytest",
        },
    }
    payload["sha256"] = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    print(json.dumps(payload, indent=2, sort_keys=True))


def bench(args: argparse.Namespace) -> None:
    fnx_graph = fnx.Graph(_make_graph(nx, args.n, args.m, args.seed))
    nx_graph = _make_graph(nx, args.n, args.m, args.seed)
    for _ in range(5):
        _call(args.mode, fnx_graph, nx_graph, args.u, args.v)
    samples: list[float] = []
    result: set[Any] = set()
    gc_was_enabled = gc.isenabled()
    gc.disable()
    try:
        for _ in range(args.repeats):
            start = time.perf_counter()
            for _ in range(args.loops):
                result = _call(args.mode, fnx_graph, nx_graph, args.u, args.v)
            samples.append((time.perf_counter() - start) / args.loops)
    finally:
        if gc_was_enabled:
            gc.enable()
    payload = {
        "mode": args.mode,
        "n": args.n,
        "m": args.m,
        "seed": args.seed,
        "u": args.u,
        "v": args.v,
        "loops": args.loops,
        "repeats": args.repeats,
        "median": statistics.median(samples),
        "mean": statistics.fmean(samples),
        "min": min(samples),
        "stdev": statistics.stdev(samples) if len(samples) > 1 else 0.0,
        "sha256": _sha(result),
        "samples": samples,
    }
    print(json.dumps(payload, sort_keys=True))


def profile(args: argparse.Namespace) -> None:
    fnx_graph = fnx.Graph(_make_graph(nx, args.n, args.m, args.seed))
    nx_graph = _make_graph(nx, args.n, args.m, args.seed)
    profiler = cProfile.Profile()
    profiler.enable()
    result: set[Any] = set()
    for _ in range(args.loops):
        result = _call(args.mode, fnx_graph, nx_graph, args.u, args.v)
    profiler.disable()
    output = io.StringIO()
    pstats.Stats(profiler, stream=output).sort_stats("cumulative").print_stats(args.limit)
    print(f"mode={args.mode} sha256={_sha(result)}")
    print(output.getvalue(), end="")


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("golden").set_defaults(func=golden)
    for name, func in (("bench", bench), ("profile", profile)):
        cmd = sub.add_parser(name)
        cmd.add_argument("--mode", choices=["old", "new", "nx"], required=True)
        cmd.add_argument("--n", type=int, default=1200)
        cmd.add_argument("--m", type=int, default=4)
        cmd.add_argument("--seed", type=int, default=17)
        cmd.add_argument("--u", type=int, default=0)
        cmd.add_argument("--v", type=int, default=10)
        cmd.add_argument("--loops", type=int, default=5000)
        if name == "bench":
            cmd.add_argument("--repeats", type=int, default=15)
        else:
            cmd.add_argument("--limit", type=int, default=50)
        cmd.set_defaults(func=func)
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
