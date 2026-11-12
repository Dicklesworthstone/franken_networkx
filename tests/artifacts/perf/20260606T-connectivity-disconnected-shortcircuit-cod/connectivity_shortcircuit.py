#!/usr/bin/env python3
"""Benchmark/proof harness for br-r37-c1-c1gz0."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import networkx as nx

import franken_networkx as fnx


def disconnected_selfloop_graph(mod: Any, *, directed: bool = False, n: int = 1500, m: int = 1200) -> Any:
    cls = mod.DiGraph if directed else mod.Graph
    graph = cls()
    graph.add_nodes_from(range(n))
    rng = random.Random(20260606)
    for _ in range(m):
        u = rng.randrange(n - 1)
        v = rng.randrange(n - 1)
        graph.add_edge(u, v)
    graph.add_edge(0, 0)
    return graph


def time_loop(func: Callable[[], Any], *, iterations: int) -> dict[str, Any]:
    start = time.perf_counter()
    result = None
    for _ in range(iterations):
        result = func()
    elapsed = time.perf_counter() - start
    return {
        "iterations": iterations,
        "elapsed_seconds": elapsed,
        "seconds_per_call": elapsed / iterations,
        "result": result,
    }


def old_delegated_node(graph: Any) -> int:
    return fnx._call_networkx_for_parity("node_connectivity", graph)


def old_delegated_edge(graph: Any) -> int:
    return fnx._call_networkx_for_parity("edge_connectivity", graph)


def proof_payload() -> dict[str, Any]:
    rows: list[dict[str, Any]] = []

    def unreachable_flow(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("flow_func must not be called on disconnected global connectivity")

    for directed in (False, True):
        fnx_graph = disconnected_selfloop_graph(fnx, directed=directed, n=80, m=50)
        nx_graph = disconnected_selfloop_graph(nx, directed=directed, n=80, m=50)
        for name in ("node_connectivity", "edge_connectivity"):
            fnx_fn = getattr(fnx, name)
            nx_fn = getattr(nx, name)
            rows.append({
                "case": f"{name}:{'directed' if directed else 'undirected'}",
                "fnx": fnx_fn(fnx_graph),
                "nx": nx_fn(nx_graph),
            })
            rows.append({
                "case": f"{name}:flow_func:{'directed' if directed else 'undirected'}",
                "fnx": fnx_fn(fnx_graph, flow_func=unreachable_flow),
                "nx": nx_fn(nx_graph, flow_func=unreachable_flow),
            })
        rows.append({
            "case": f"edge_connectivity:cutoff:{'directed' if directed else 'undirected'}",
            "fnx": fnx.edge_connectivity(fnx_graph, cutoff=2),
            "nx": nx.edge_connectivity(nx_graph, cutoff=2),
        })
        rows.append({
            "case": f"node_connectivity:local:{'directed' if directed else 'undirected'}",
            "fnx": fnx.node_connectivity(fnx_graph, 0, 79),
            "nx": nx.node_connectivity(nx_graph, 0, 79),
        })
        rows.append({
            "case": f"edge_connectivity:local:{'directed' if directed else 'undirected'}",
            "fnx": fnx.edge_connectivity(fnx_graph, 0, 79),
            "nx": nx.edge_connectivity(nx_graph, 0, 79),
        })

    payload = {
        "bead": "br-r37-c1-c1gz0",
        "rows": rows,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    payload["sha256"] = hashlib.sha256(encoded).hexdigest()
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", required=True)
    parser.add_argument("--iterations", type=int, default=20)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    graph = disconnected_selfloop_graph(fnx)
    cases: dict[str, Callable[[], Any]] = {
        "before-node": lambda: old_delegated_node(graph),
        "after-node": lambda: fnx.node_connectivity(graph),
        "before-edge": lambda: old_delegated_edge(graph),
        "after-edge": lambda: fnx.edge_connectivity(graph),
        "nx-node": lambda: nx.node_connectivity(disconnected_selfloop_graph(nx)),
        "nx-edge": lambda: nx.edge_connectivity(disconnected_selfloop_graph(nx)),
    }

    if args.mode == "proof":
        payload = proof_payload()
    elif args.mode in cases:
        payload = {
            "bead": "br-r37-c1-c1gz0",
            "mode": args.mode,
            **time_loop(cases[args.mode], iterations=args.iterations),
        }
    else:
        raise SystemExit(f"unknown mode: {args.mode}")

    text = json.dumps(payload, sort_keys=True, indent=2)
    if args.output is not None:
        args.output.write_text(text + "\n", encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
