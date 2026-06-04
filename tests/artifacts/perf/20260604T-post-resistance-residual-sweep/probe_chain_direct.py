#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import time
from typing import Any

import franken_networkx as fnx
import networkx as nx


def _cycle_chain(module: Any, n: int) -> Any:
    graph = module.cycle_graph(n)
    graph.add_edges_from((i, (i + 3) % n) for i in range(0, n, 3))
    return graph


def chain_direct(G, root=None):
    if root is not None and root not in G:
        raise fnx.NodeNotFound(f"Root node {root} is not in graph")

    H = fnx.DiGraph()
    nodes = []
    for u, v, label in fnx.dfs_labeled_edges(G, source=root):
        if label == "forward":
            if u == v:
                H.add_node(v, parent=None)
                nodes.append(v)
            else:
                H.add_node(v, parent=u)
                H.add_edge(v, u, nontree=False)
                nodes.append(v)
        elif label == "nontree" and v not in H[u]:
            H.add_edge(v, u, nontree=True)

    def build_chain(u, v, visited):
        while v not in visited:
            yield u, v
            visited.add(v)
            u, v = v, H.nodes[v]["parent"]
        yield u, v

    visited = set()
    for u in nodes:
        visited.add(u)
        edges = ((u, v) for u, v, d in H.out_edges(u, data="nontree") if d)
        for u, v in edges:
            yield list(build_chain(u, v, visited))


def _stable(value: Any) -> Any:
    return [[repr(u), repr(v)] for chain in value for u, v in chain]


def _digest(value: Any) -> str:
    payload = json.dumps(_stable(value), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def _time(func, graph, repeats):
    samples = []
    digest = ""
    for _ in range(repeats):
        started = time.perf_counter()
        value = list(func(graph))
        samples.append(time.perf_counter() - started)
        digest = _digest(value)
    return {
        "mean_sec": statistics.fmean(samples),
        "median_sec": statistics.median(samples),
        "min_sec": min(samples),
        "max_sec": max(samples),
        "samples_sec": samples,
        "digest": digest,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=250)
    parser.add_argument("--repeats", type=int, default=25)
    args = parser.parse_args()

    graph_f = _cycle_chain(fnx, args.n)
    graph_n = _cycle_chain(nx, args.n)
    rows = {
        "fnx_current": _time(fnx.chain_decomposition, graph_f, args.repeats),
        "fnx_direct": _time(chain_direct, graph_f, args.repeats),
        "nx": _time(nx.chain_decomposition, graph_n, args.repeats),
    }
    print(json.dumps(rows, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
