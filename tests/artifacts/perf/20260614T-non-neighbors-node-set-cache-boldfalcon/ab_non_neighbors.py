#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json

import franken_networkx as fnx


def _edge_rows(n: int, degree: int) -> list[tuple[int, int]]:
    return [
        (u, (u + step * 7) % n)
        for u in range(n)
        for step in range(1, degree + 1)
    ]


def _make_graph(n: int, degree: int) -> fnx.DiGraph:
    graph = fnx.DiGraph()
    graph.add_nodes_from(range(n))
    graph.add_edges_from(_edge_rows(n, degree))
    return graph


def _old_equivalent(graph: fnx.DiGraph, node: int) -> set[int]:
    hash(node)
    if node not in graph:
        raise KeyError(node)
    raw_nbrs = fnx._raw_neighbors_dispatch(graph)
    native_keys = getattr(graph, "_native_node_keys", None)
    if native_keys is not None:
        nodes = set(native_keys())
        if raw_nbrs is not None:
            nbrs = set(raw_nbrs(graph, node))
        else:
            nbrs = set(graph[node])
        return nodes - nbrs - {node}
    if raw_nbrs is not None:
        return set(graph) - set(raw_nbrs(graph, node)) - {node}
    return set(graph.adj) - set(graph.adj[node]) - {node}


def _digest(values: set[int]) -> str:
    payload = json.dumps(sorted(values), separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["old", "new"])
    parser.add_argument("--n", type=int, default=5000)
    parser.add_argument("--degree", type=int, default=8)
    parser.add_argument("--node", type=int, default=0)
    parser.add_argument("--loops", type=int, default=3000)
    args = parser.parse_args()

    graph = _make_graph(args.n, args.degree)
    call = (
        (lambda: _old_equivalent(graph, args.node))
        if args.mode == "old"
        else (lambda: set(fnx.non_neighbors(graph, args.node)))
    )
    result: set[int] = set()
    for _ in range(args.loops):
        result = call()
    print(_digest(result))


if __name__ == "__main__":
    main()
