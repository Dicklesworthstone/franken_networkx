from __future__ import annotations

import json
import statistics
import sys
import time

import networkx as nx
import franken_networkx as fnx


def _build(module, n: int, extra_edges: int):
    graph = module.Graph()
    graph.add_nodes_from(range(n))
    graph.add_edges_from((i, i + 1) for i in range(n - 1))
    for i in range(extra_edges):
        u = (i * 37 + 11) % n
        v = (i * 53 + 97) % n
        if u != v:
            graph.add_edge(u, v, weight=i % 7)
    return graph


def _time_copy(module, n: int, keep_size: int, extra_edges: int, copies: int):
    graph = _build(module, n, extra_edges)
    keep = [(i * 41 + 7) % n for i in range(keep_size)]
    for _ in range(3):
        graph.subgraph(keep).copy()
    samples = []
    edge_count = None
    node_order = None
    for _ in range(9):
        start = time.perf_counter()
        for _ in range(copies):
            copied = graph.subgraph(keep).copy()
        elapsed = time.perf_counter() - start
        samples.append(elapsed)
        edge_count = copied.number_of_edges()
        node_order = list(copied.nodes())[:12]
    return {
        "module": module.__name__,
        "n": n,
        "keep_size": keep_size,
        "extra_edges": extra_edges,
        "copies": copies,
        "min_s": min(samples),
        "median_s": statistics.median(samples),
        "p95_s": sorted(samples)[int(len(samples) * 0.95) - 1],
        "edge_count": edge_count,
        "node_order_head": node_order,
    }


def main() -> None:
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 2000
    keep_size = int(sys.argv[2]) if len(sys.argv) > 2 else 50
    extra_edges = int(sys.argv[3]) if len(sys.argv) > 3 else 8000
    copies = int(sys.argv[4]) if len(sys.argv) > 4 else 50
    rows = [
        _time_copy(nx, n, keep_size, extra_edges, copies),
        _time_copy(fnx, n, keep_size, extra_edges, copies),
    ]
    print(json.dumps(rows, sort_keys=True))


if __name__ == "__main__":
    main()
