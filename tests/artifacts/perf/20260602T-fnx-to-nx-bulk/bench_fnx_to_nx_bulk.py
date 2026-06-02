#!/usr/bin/env python3
"""Benchmark/proof harness for br-r37-c1-xykjs.

The measured lever is only the `_fnx_to_nx` simple-graph conversion path:
`fallback` disables the native bulk helper at runtime; `native` enables it.
Graph construction is outside the timed loop.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from collections.abc import Mapping

import franken_networkx as fnx
import franken_networkx.backend as backend
import networkx as nx


def _stable_attrs(attrs: Mapping) -> list[list[str]]:
    return [[repr(k), repr(v)] for k, v in sorted(attrs.items(), key=lambda kv: repr(kv[0]))]


def graph_digest(graph) -> str:
    payload = {
        "directed": graph.is_directed(),
        "multigraph": graph.is_multigraph(),
        "graph_attrs": _stable_attrs(graph.graph),
        "nodes": [],
        "adjacency": [],
    }
    for node in graph:
        payload["nodes"].append([repr(node), _stable_attrs(graph.nodes[node])])
    for node in graph:
        nbrs = []
        for nbr in graph.adj[node]:
            nbrs.append([repr(nbr), _stable_attrs(graph[node][nbr])])
        payload["adjacency"].append([repr(node), nbrs])
    data = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    return hashlib.sha256(data).hexdigest()


def result_digest(result) -> str:
    data = json.dumps(result, separators=(",", ":"), sort_keys=True).encode()
    return hashlib.sha256(data).hexdigest()


def make_graphs(n: int, m: int, seed: int):
    source = nx.barabasi_albert_graph(n, m, seed=seed)
    fg = fnx.Graph()
    gt = nx.Graph()
    fg.add_nodes_from(source.nodes())
    gt.add_nodes_from(source.nodes())
    for u, v in source.edges():
        attrs = {"weight": (u * 31 + v * 17) % 11, "tag": f"{u}:{v}"}
        fg.add_edge(u, v, **attrs)
        gt.add_edge(u, v, **attrs)
    fg.graph["seed"] = seed
    gt.graph["seed"] = seed
    return fg, gt


def set_native_mode(mode: str):
    helper = getattr(backend, "_native_fnx_to_nx_adjacency", None)
    if mode == "fallback":
        backend._native_fnx_to_nx_adjacency = None
    elif mode == "native":
        if helper is None:
            raise RuntimeError("native fnx_to_nx_adjacency helper is unavailable")
    return helper


def run(args: argparse.Namespace) -> dict:
    fg, gt = make_graphs(args.nodes, args.m, args.seed)
    helper = set_native_mode(args.mode)
    try:
        start = time.perf_counter()
        digest = ""
        for _ in range(args.repeat):
            if args.workload == "convert":
                digest = graph_digest(backend._fnx_to_nx(fg))
            elif args.workload == "onion":
                if args.mode == "nx":
                    digest = result_digest(nx.onion_layers(gt))
                else:
                    digest = result_digest(fnx.onion_layers(fg))
            elif args.workload == "nx-build":
                rebuilt = nx.Graph()
                rebuilt.add_nodes_from(gt.nodes(data=True))
                rebuilt.add_edges_from((u, v, dict(a)) for u, v, a in gt.edges(data=True))
                rebuilt.graph.update(dict(gt.graph))
                digest = graph_digest(rebuilt)
            else:
                raise AssertionError(args.workload)
        elapsed = time.perf_counter() - start
    finally:
        backend._native_fnx_to_nx_adjacency = helper
    return {
        "mode": args.mode,
        "workload": args.workload,
        "nodes": args.nodes,
        "edges": fg.number_of_edges(),
        "repeat": args.repeat,
        "elapsed_s": elapsed,
        "sha256": digest,
        "expected_graph_sha256": graph_digest(gt),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workload", choices=["convert", "onion", "nx-build"], required=True)
    parser.add_argument("--mode", choices=["fallback", "native", "nx"], required=True)
    parser.add_argument("--nodes", type=int, default=3000)
    parser.add_argument("--m", type=int, default=4)
    parser.add_argument("--seed", type=int, default=11)
    parser.add_argument("--repeat", type=int, default=3)
    args = parser.parse_args()
    if args.mode == "nx" and args.workload not in {"onion", "nx-build"}:
        raise SystemExit("--mode nx is only valid for onion or nx-build")
    print(json.dumps(run(args), sort_keys=True))


if __name__ == "__main__":
    main()
