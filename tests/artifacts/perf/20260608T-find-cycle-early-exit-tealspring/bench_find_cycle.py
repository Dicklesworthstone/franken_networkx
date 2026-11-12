from __future__ import annotations

import json
import random
import sys
from time import perf_counter

import networkx as nx

import franken_networkx as fnx


def _fixture_edges(nodes: int = 1500, edges: int = 9000):
    result = [(0, 1), (1, 2), (2, 0)]
    seen = set(result)
    rng = random.Random(57)
    while len(result) < edges:
        source = rng.randrange(nodes)
        target = rng.randrange(nodes)
        if source != target and (source, target) not in seen:
            seen.add((source, target))
            result.append((source, target))
    return result


def _build_graph(module):
    graph = module.DiGraph()
    graph.add_edges_from(_fixture_edges())
    return graph


def _serialize_cycle(cycle):
    return [[repr(part) for part in edge] for edge in cycle]


def main() -> int:
    module_name = sys.argv[1] if len(sys.argv) > 1 else "fnx"
    repeats = int(sys.argv[2]) if len(sys.argv) > 2 else 200
    module = nx if module_name == "nx" else fnx
    graph = _build_graph(module)

    checksum = 0
    last = None
    start = perf_counter()
    for _ in range(repeats):
        if module_name == "fnx-old":
            last = fnx._call_networkx_for_parity("find_cycle", graph)
        else:
            last = module.find_cycle(graph)
        checksum ^= hash(tuple(last)) & 0xFFFFFFFF
    elapsed = perf_counter() - start

    print(
        json.dumps(
            {
                "module": module_name,
                "nodes": graph.number_of_nodes(),
                "edges": graph.number_of_edges(),
                "repeats": repeats,
                "elapsed_seconds": elapsed,
                "checksum": checksum,
                "last": _serialize_cycle(last),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
