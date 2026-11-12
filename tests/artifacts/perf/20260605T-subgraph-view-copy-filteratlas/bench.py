from __future__ import annotations

import json
import statistics
import sys
import time

import networkx as nx
import franken_networkx as fnx


def _install_legacy_fnx_subgraph_filter():
    def legacy_filter(graph, nbunch):
        if nbunch is None:
            return None
        if nbunch in graph:
            allowed_nodes = {nbunch}
        else:
            allowed_nodes = set()
            for node in nbunch:
                if node in graph:
                    allowed_nodes.add(node)
        return lambda node: node in allowed_nodes

    fnx._subgraph_filter_from_nbunch = legacy_filter


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
    args = list(sys.argv[1:])
    module_name = "both"
    if "--legacy-fnx" in args:
        args.remove("--legacy-fnx")
        _install_legacy_fnx_subgraph_filter()
    if "--module" in args:
        index = args.index("--module")
        module_name = args[index + 1]
        del args[index : index + 2]
    n = int(args[0]) if len(args) > 0 else 2000
    keep_size = int(args[1]) if len(args) > 1 else 50
    extra_edges = int(args[2]) if len(args) > 2 else 8000
    copies = int(args[3]) if len(args) > 3 else 50
    modules = {"nx": nx, "fnx": fnx}
    if module_name == "both":
        selected = [nx, fnx]
    else:
        selected = [modules[module_name]]
    rows = [_time_copy(module, n, keep_size, extra_edges, copies) for module in selected]
    print(json.dumps(rows, sort_keys=True))


if __name__ == "__main__":
    main()
