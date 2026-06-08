from __future__ import annotations

import argparse
import json
import statistics
import time

import franken_networkx as fnx
from franken_networkx.backend import _fnx_to_nx
from franken_networkx._fnx import fnx_to_nx_adjacency


def build_graph(n: int, degree: int, *, directed: bool = False):
    graph = fnx.DiGraph() if directed else fnx.Graph()
    nodes = list(range(n))
    graph.add_nodes_from(nodes)
    for source in nodes:
        for offset in range(1, degree + 1):
            target = (source + offset) % n
            if directed or source <= target:
                graph.add_edge(source, target, weight=(source * 131 + target) % 17)
    graph.graph["name"] = "align_rows_bench"
    return graph


def time_call(fn, repeats: int) -> list[float]:
    samples = []
    for _ in range(repeats):
        start = time.perf_counter()
        fn()
        samples.append(time.perf_counter() - start)
    return samples


def summarize(samples: list[float]) -> dict[str, float]:
    ordered = sorted(samples)
    return {
        "min": ordered[0],
        "median": statistics.median(ordered),
        "mean": statistics.fmean(ordered),
        "max": ordered[-1],
        "p95": ordered[min(len(ordered) - 1, int(len(ordered) * 0.95))],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=800)
    parser.add_argument("--degree", type=int, default=10)
    parser.add_argument("--repeats", type=int, default=15)
    parser.add_argument("--directed", action="store_true")
    parser.add_argument("--mode", choices=["convert", "rows", "bulk", "planarity"], default="convert")
    args = parser.parse_args()

    graph = build_graph(args.n, args.degree, directed=args.directed)

    if args.mode == "convert":
        def op():
            converted = _fnx_to_nx(graph)
            return converted.number_of_edges()
    elif args.mode == "rows":
        row_map = graph.adj

        def op():
            return sum(len(list(row_map[node])) for node in graph)
    elif args.mode == "bulk":
        def op():
            return sum(len(row) for _, row in fnx_to_nx_adjacency(graph))
    else:
        if args.directed:
            raise SystemExit("planarity mode expects an undirected graph")

        def op():
            return fnx.check_planarity(graph, counterexample=False)[0]

    result = op()
    samples = time_call(op, args.repeats)
    payload = {
        "mode": args.mode,
        "directed": args.directed,
        "n": args.n,
        "degree": args.degree,
        "edges": graph.number_of_edges(),
        "result": result,
        "samples": samples,
        "summary": summarize(samples),
    }
    print(json.dumps(payload, sort_keys=True))


if __name__ == "__main__":
    main()
