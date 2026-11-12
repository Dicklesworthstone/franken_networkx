#!/usr/bin/env python3
"""Benchmark and golden harness for DiGraph predecessor/successor row iteration."""

from __future__ import annotations

import argparse
import cProfile
import hashlib
import io
import json
import pstats
import time
from pathlib import Path
from typing import Any, Callable

import franken_networkx as fnx
import networkx as nx


NODES = 1800
PROBABILITY = 0.006
SEED = 15


def make_graphs() -> tuple[fnx.DiGraph, nx.DiGraph]:
    reference = nx.gnp_random_graph(NODES, PROBABILITY, seed=SEED, directed=True)
    graph = fnx.DiGraph()
    graph.add_nodes_from(reference.nodes())
    graph.add_edges_from(reference.edges())
    return graph, reference


def predecessors_all(graph: Any) -> list[list[Any]]:
    return [list(graph.predecessors(node)) for node in graph.nodes()]


def successors_all(graph: Any) -> list[list[Any]]:
    return [list(graph.successors(node)) for node in graph.nodes()]


def workload(kind: str) -> Callable[[Any], Any]:
    if kind == "pred":
        return predecessors_all
    if kind == "succ":
        return successors_all
    if kind == "both":
        return lambda graph: {
            "predecessors": predecessors_all(graph),
            "successors": successors_all(graph),
        }
    raise ValueError(f"unknown workload kind {kind!r}")


def stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=repr)


def sha256_obj(value: Any) -> str:
    return hashlib.sha256(stable_json(value).encode("utf-8")).hexdigest()


def exception_record(func: Callable[[], Any]) -> dict[str, str] | None:
    try:
        func()
    except Exception as exc:  # noqa: BLE001 - exception class/message are golden data.
        return {"type": type(exc).__name__, "message": str(exc)}
    return None


def first_node_with_predecessor(graph: Any) -> Any:
    for node in graph.nodes():
        preds = list(graph.predecessors(node))
        if preds:
            return node
    raise AssertionError("fixture unexpectedly has no predecessor rows")


def first_node_with_successor(graph: Any) -> Any:
    for node in graph.nodes():
        succs = list(graph.successors(node))
        if succs:
            return node
    raise AssertionError("fixture unexpectedly has no successor rows")


def mutation_record(graph: Any, method: str) -> dict[str, str | None]:
    if method == "predecessors":
        node = first_node_with_predecessor(graph)
        iterator = graph.predecessors(node)
        next(iterator)
        graph.add_edge(NODES + 7, node)
    else:
        node = first_node_with_successor(graph)
        iterator = graph.successors(node)
        next(iterator)
        graph.add_edge(node, NODES + 7)
    try:
        next(iterator)
    except Exception as exc:  # noqa: BLE001 - exception class/message are golden data.
        return {"type": type(exc).__name__, "message": str(exc)}
    return {"type": None, "message": None}


def golden() -> dict[str, Any]:
    graph, reference = make_graphs()
    pred_fnx = predecessors_all(graph)
    pred_nx = predecessors_all(reference)
    succ_fnx = successors_all(graph)
    succ_nx = successors_all(reference)

    missing = {
        "fnx_predecessors": exception_record(lambda: list(graph.predecessors("missing"))),
        "nx_predecessors": exception_record(lambda: list(reference.predecessors("missing"))),
        "fnx_successors": exception_record(lambda: list(graph.successors("missing"))),
        "nx_successors": exception_record(lambda: list(reference.successors("missing"))),
    }
    unhashable = {
        "fnx_predecessors": exception_record(lambda: list(graph.predecessors(["x"]))),
        "nx_predecessors": exception_record(lambda: list(reference.predecessors(["x"]))),
        "fnx_successors": exception_record(lambda: list(graph.successors(["x"]))),
        "nx_successors": exception_record(lambda: list(reference.successors(["x"]))),
    }

    mutation_fnx_pred, mutation_nx_pred = make_graphs()
    mutation_fnx_succ, mutation_nx_succ = make_graphs()
    mutation = {
        "fnx_predecessors": mutation_record(mutation_fnx_pred, "predecessors"),
        "nx_predecessors": mutation_record(mutation_nx_pred, "predecessors"),
        "fnx_successors": mutation_record(mutation_fnx_succ, "successors"),
        "nx_successors": mutation_record(mutation_nx_succ, "successors"),
    }

    payload = {
        "fixture": {"nodes": NODES, "probability": PROBABILITY, "seed": SEED},
        "predecessors": {
            "match": pred_fnx == pred_nx,
            "fnx_sha256": sha256_obj(pred_fnx),
            "nx_sha256": sha256_obj(pred_nx),
            "rows": len(pred_fnx),
        },
        "successors": {
            "match": succ_fnx == succ_nx,
            "fnx_sha256": sha256_obj(succ_fnx),
            "nx_sha256": sha256_obj(succ_nx),
            "rows": len(succ_fnx),
        },
        "missing": missing,
        "unhashable": unhashable,
        "mutation": mutation,
    }
    payload["golden_sha256"] = sha256_obj(payload)
    return payload


def bench_one(graph: Any, kind: str, loops: int) -> dict[str, Any]:
    op = workload(kind)
    out = op(graph)
    start = time.perf_counter()
    for _ in range(loops):
        out = op(graph)
    elapsed = time.perf_counter() - start
    return {
        "kind": kind,
        "loops": loops,
        "elapsed_s": elapsed,
        "seconds_per_loop": elapsed / loops,
        "output_sha256": sha256_obj(out),
    }


def profile_fnx(kind: str, loops: int, output: Path) -> dict[str, Any]:
    graph, _ = make_graphs()
    op = workload(kind)
    op(graph)
    profiler = cProfile.Profile()
    profiler.enable()
    for _ in range(loops):
        op(graph)
    profiler.disable()

    text_stream = io.StringIO()
    stats = pstats.Stats(profiler, stream=text_stream).strip_dirs().sort_stats("cumtime")
    stats.print_stats(30)
    output.write_text(text_stream.getvalue(), encoding="utf-8")
    return {"kind": kind, "loops": loops, "profile_text": str(output)}


def write_or_print(payload: Any, output: Path | None) -> None:
    text = json.dumps(payload, indent=2, sort_keys=True)
    if output is None:
        print(text)
    else:
        output.write_text(text + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="cmd", required=True)

    for name in ("bench-fnx", "bench-nx"):
        bench_parser = subparsers.add_parser(name)
        bench_parser.add_argument("--kind", choices=("pred", "succ", "both"), default="pred")
        bench_parser.add_argument("--loops", type=int, default=200)
        bench_parser.add_argument("--output", type=Path)

    golden_parser = subparsers.add_parser("golden")
    golden_parser.add_argument("--output", type=Path)

    profile_parser = subparsers.add_parser("profile-fnx")
    profile_parser.add_argument("--kind", choices=("pred", "succ", "both"), default="pred")
    profile_parser.add_argument("--loops", type=int, default=120)
    profile_parser.add_argument("--output", type=Path, required=True)
    profile_parser.add_argument("--json-output", type=Path)

    args = parser.parse_args()
    if args.cmd == "golden":
        write_or_print(golden(), args.output)
    elif args.cmd == "bench-fnx":
        graph, _ = make_graphs()
        write_or_print(bench_one(graph, args.kind, args.loops), args.output)
    elif args.cmd == "bench-nx":
        _, reference = make_graphs()
        write_or_print(bench_one(reference, args.kind, args.loops), args.output)
    elif args.cmd == "profile-fnx":
        result = profile_fnx(args.kind, args.loops, args.output)
        write_or_print(result, args.json_output)


if __name__ == "__main__":
    main()
