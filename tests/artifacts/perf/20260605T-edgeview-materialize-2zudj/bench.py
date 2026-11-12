from __future__ import annotations

import json
import statistics
import sys
import time

import franken_networkx as fnx
import networkx as nx


def _build(module, n: int, extra_edges: int):
    graph = module.Graph()
    graph.add_nodes_from(range(n))
    graph.add_edges_from((i, i + 1, {"weight": i % 7}) for i in range(n - 1))
    for i in range(extra_edges):
        u = (i * 37 + 11) % n
        v = (i * 53 + 97) % n
        if u != v:
            graph.add_edge(u, v, weight=(i + 3) % 11)
    return graph


def _time_edges(module, data: bool, n: int, extra_edges: int, reps: int):
    graph = _build(module, n, extra_edges)
    for _ in range(3):
        list(graph.edges(data=data))
    samples = []
    length = None
    head = None
    for _ in range(9):
        start = time.perf_counter()
        for _ in range(reps):
            rows = list(graph.edges(data=data))
        elapsed = time.perf_counter() - start
        samples.append(elapsed)
        length = len(rows)
        head = rows[:8]
    return {
        "module": module.__name__,
        "data": data,
        "n": n,
        "extra_edges": extra_edges,
        "reps": reps,
        "edge_rows": length,
        "head": head,
        "min_s": min(samples),
        "median_s": statistics.median(samples),
        "p95_s": sorted(samples)[int(len(samples) * 0.95) - 1],
    }


def main() -> None:
    args = list(sys.argv[1:])
    module_name = "fnx"
    data = True
    if "--module" in args:
        index = args.index("--module")
        module_name = args[index + 1]
        del args[index : index + 2]
    if "--data" in args:
        index = args.index("--data")
        data = args[index + 1].lower() == "true"
        del args[index : index + 2]
    n = int(args[0]) if len(args) > 0 else 4000
    extra_edges = int(args[1]) if len(args) > 1 else 16000
    reps = int(args[2]) if len(args) > 2 else 30
    modules = {"fnx": fnx, "nx": nx}
    print(
        json.dumps(
            [_time_edges(modules[module_name], data, n, extra_edges, reps)],
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
