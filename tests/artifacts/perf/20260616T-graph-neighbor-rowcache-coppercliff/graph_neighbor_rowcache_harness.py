#!/usr/bin/env python3
"""Benchmark and golden harness for Graph.neighbors() row iteration."""

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
from typing import Any, Callable

import franken_networkx as fnx
import networkx as nx


NODES = 2400
PROBABILITY = 0.0045
SEED = 23


def repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def head_metadata() -> dict[str, object]:
    root = repo_root()
    try:
        head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
        short = subprocess.check_output(
            ["git", "log", "-1", "--oneline"],
            cwd=root,
            text=True,
        ).strip()
    except Exception:
        head = "unknown"
        short = "unknown"
    return {
        "head": head,
        "head_short": short,
        "repo_root": str(root),
        "python": sys.version,
        "franken_networkx_file": fnx.__file__,
        "networkx_file": nx.__file__,
        "networkx_version": nx.__version__,
        "graph": {
            "family": "Graph(gnp_random_graph(n, p, seed))",
            "n": NODES,
            "p": PROBABILITY,
            "seed": SEED,
        },
        "workload": "[list(G.neighbors(n)) for n in G.nodes()]",
    }


def build_nx_graph() -> nx.Graph:
    return nx.gnp_random_graph(NODES, PROBABILITY, seed=SEED, directed=False)


def build_fnx_graph(source: nx.Graph) -> fnx.Graph:
    graph = fnx.Graph()
    graph.add_nodes_from(source.nodes())
    graph.add_edges_from(source.edges())
    return graph


def make_graphs() -> tuple[fnx.Graph, nx.Graph]:
    reference = build_nx_graph()
    return build_fnx_graph(reference), reference


def neighbors_all(graph: Any) -> list[list[Any]]:
    return [list(graph.neighbors(node)) for node in graph.nodes()]


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


def first_node_with_neighbor(graph: Any) -> Any:
    for node in graph.nodes():
        if list(graph.neighbors(node)):
            return node
    raise AssertionError("fixture unexpectedly has no neighbor rows")


def mutation_record(graph: Any) -> dict[str, str | None]:
    node = first_node_with_neighbor(graph)
    iterator = graph.neighbors(node)
    first = next(iterator)
    graph.add_edge(node, NODES + 7)
    try:
        next(iterator)
    except Exception as exc:  # noqa: BLE001 - exception class/message are golden data.
        return {"first": first, "type": type(exc).__name__, "message": str(exc)}
    return {"first": first, "type": None, "message": None}


def private_override_record(module: Any) -> list[Any]:
    graph = module.Graph()
    graph.add_nodes_from([0, 1, 2])
    graph._adj = {
        0: {2: {"weight": 1}, 1: {"weight": 1}},
        1: {0: {"weight": 1}},
        2: {0: {"weight": 1}},
    }
    return list(graph.neighbors(0))


def golden() -> dict[str, Any]:
    graph, reference = make_graphs()
    fnx_rows = neighbors_all(graph)
    nx_rows = neighbors_all(reference)

    mutation_fnx, mutation_nx = make_graphs()
    payload = {
        "fixture": {"nodes": NODES, "probability": PROBABILITY, "seed": SEED},
        "neighbors": {
            "match": fnx_rows == nx_rows,
            "fnx_sha256": sha256_obj(fnx_rows),
            "nx_sha256": sha256_obj(nx_rows),
            "rows": len(fnx_rows),
            "samples": {
                "first_5": nx_rows[:5],
                "last_5": nx_rows[-5:],
            },
        },
        "missing": {
            "fnx": exception_record(lambda: list(graph.neighbors("missing"))),
            "nx": exception_record(lambda: list(reference.neighbors("missing"))),
        },
        "unhashable": {
            "fnx": exception_record(lambda: list(graph.neighbors(["x"]))),
            "nx": exception_record(lambda: list(reference.neighbors(["x"]))),
        },
        "mutation": {
            "fnx": mutation_record(mutation_fnx),
            "nx": mutation_record(mutation_nx),
        },
        "private_override": {
            "fnx": private_override_record(fnx),
            "nx": private_override_record(nx),
        },
        "metadata": head_metadata(),
    }
    payload["golden_sha256"] = sha256_obj(payload)
    return payload


def bench_one(graph: Any, loops: int) -> dict[str, Any]:
    out = neighbors_all(graph)
    start = time.perf_counter()
    for _ in range(loops):
        out = neighbors_all(graph)
    elapsed = time.perf_counter() - start
    return {
        "loops": loops,
        "elapsed_s": elapsed,
        "seconds_per_loop": elapsed / loops,
        "output_sha256": sha256_obj(out),
        "metadata": head_metadata(),
    }


def profile_fnx(loops: int, output: Path) -> dict[str, Any]:
    graph, _ = make_graphs()
    neighbors_all(graph)
    profiler = cProfile.Profile()
    profiler.enable()
    for _ in range(loops):
        neighbors_all(graph)
    profiler.disable()

    text_stream = io.StringIO()
    stats = pstats.Stats(profiler, stream=text_stream).strip_dirs().sort_stats("cumtime")
    stats.print_stats(40)
    output.write_text(text_stream.getvalue(), encoding="utf-8")
    return {"loops": loops, "profile_text": str(output), "metadata": head_metadata()}


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
        bench_parser.add_argument("--loops", type=int, default=200)
        bench_parser.add_argument("--output", type=Path)

    golden_parser = subparsers.add_parser("golden")
    golden_parser.add_argument("--output", type=Path)

    profile_parser = subparsers.add_parser("profile-fnx")
    profile_parser.add_argument("--loops", type=int, default=100)
    profile_parser.add_argument("--output", type=Path, required=True)
    profile_parser.add_argument("--json-output", type=Path)

    args = parser.parse_args()
    if args.cmd == "golden":
        write_or_print(golden(), args.output)
    elif args.cmd == "bench-fnx":
        graph, _ = make_graphs()
        write_or_print(bench_one(graph, args.loops), args.output)
    elif args.cmd == "bench-nx":
        _, reference = make_graphs()
        write_or_print(bench_one(reference, args.loops), args.output)
    elif args.cmd == "profile-fnx":
        result = profile_fnx(args.loops, args.output)
        write_or_print(result, args.json_output)


if __name__ == "__main__":
    main()
