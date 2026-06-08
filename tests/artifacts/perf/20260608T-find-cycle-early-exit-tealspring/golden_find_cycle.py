from __future__ import annotations

import json
import random

import networkx as nx

import franken_networkx as fnx


def _add_edges(graph, edges):
    for edge in edges:
        if graph.is_multigraph() and len(edge) == 3:
            graph.add_edge(edge[0], edge[1], key=edge[2])
        else:
            graph.add_edge(edge[0], edge[1])
    return graph


def _make(module, graph_type, edges):
    graph = getattr(module, graph_type)()
    return _add_edges(graph, edges)


def _known_divergence_edges():
    rng = random.Random(41)
    [(rng.randrange(10), rng.randrange(10)) for _ in range(28)]
    return [
        (u, v)
        for u, v in ((rng.randrange(10), rng.randrange(10)) for _ in range(28))
        if u != v
    ]


CASES = [
    {
        "name": "directed_known_divergence",
        "graph_type": "DiGraph",
        "edges": _known_divergence_edges(),
        "kwargs": {},
    },
    {
        "name": "directed_backtracking",
        "graph_type": "DiGraph",
        "edges": [(0, 1), (1, 2), (2, 3), (1, 4), (4, 1), (3, 0)],
        "kwargs": {},
    },
    {
        "name": "directed_source_scalar_late_component",
        "graph_type": "DiGraph",
        "edges": [(0, 1), (2, 3), (3, 4), (4, 2)],
        "kwargs": {"source": 2},
    },
    {
        "name": "directed_source_list_order",
        "graph_type": "DiGraph",
        "edges": [(0, 1), (1, 0), (3, 4), (4, 5), (5, 3)],
        "kwargs": {"source": [3, 0]},
    },
    {
        "name": "directed_missing_source",
        "graph_type": "DiGraph",
        "edges": [(0, 1), (1, 0)],
        "kwargs": {"source": 99},
    },
    {
        "name": "directed_orientation_original",
        "graph_type": "DiGraph",
        "edges": [(0, 1), (1, 2), (2, 0), (2, 3)],
        "kwargs": {"orientation": "original"},
    },
    {
        "name": "directed_orientation_reverse",
        "graph_type": "DiGraph",
        "edges": [(0, 1), (1, 2), (2, 0), (2, 3)],
        "kwargs": {"orientation": "reverse"},
    },
    {
        "name": "directed_orientation_ignore_dag",
        "graph_type": "DiGraph",
        "edges": [(0, 1), (0, 2), (1, 2)],
        "kwargs": {"orientation": "ignore"},
    },
    {
        "name": "directed_no_cycle",
        "graph_type": "DiGraph",
        "edges": [(0, 1), (1, 2), (2, 3)],
        "kwargs": {},
    },
    {
        "name": "directed_self_loop",
        "graph_type": "DiGraph",
        "edges": [(0, 0), (0, 1)],
        "kwargs": {},
    },
    {
        "name": "directed_invalid_orientation",
        "graph_type": "DiGraph",
        "edges": [(0, 1), (1, 0)],
        "kwargs": {"orientation": "sideways"},
    },
    {
        "name": "undirected_chord_direction",
        "graph_type": "Graph",
        "edges": [("c", "d"), ("a", "b"), ("b", "c"), ("d", "e"), ("a", "c")],
        "kwargs": {},
    },
    {
        "name": "undirected_orientation_original",
        "graph_type": "Graph",
        "edges": [(0, 1), (1, 2), (2, 0)],
        "kwargs": {"orientation": "original"},
    },
    {
        "name": "undirected_no_cycle",
        "graph_type": "Graph",
        "edges": [(0, 1), (1, 2)],
        "kwargs": {},
    },
    {
        "name": "multidigraph_key_order",
        "graph_type": "MultiDiGraph",
        "edges": [(0, 1, "a"), (1, 2, "b"), (2, 0, "c"), (1, 0, "d")],
        "kwargs": {},
    },
    {
        "name": "multidigraph_orientation_ignore",
        "graph_type": "MultiDiGraph",
        "edges": [(0, 1, "a"), (0, 2, "b"), (1, 2, "c")],
        "kwargs": {"orientation": "ignore"},
    },
    {
        "name": "multigraph_key_order",
        "graph_type": "MultiGraph",
        "edges": [(0, 1, "a"), (1, 2, "b"), (2, 0, "c"), (0, 1, "d")],
        "kwargs": {},
    },
]


def _serialize_result(module, graph, kwargs):
    try:
        return {
            "ok": [
                [repr(part) for part in edge]
                for edge in module.find_cycle(graph, **kwargs)
            ]
        }
    except Exception as exc:  # noqa: BLE001 - parity artifact records exception shape.
        return {"error": type(exc).__name__, "message": str(exc)}


def main() -> int:
    for case in CASES:
        fnx_graph = _make(fnx, case["graph_type"], case["edges"])
        nx_graph = _make(nx, case["graph_type"], case["edges"])
        record = {
            "name": case["name"],
            "graph_type": case["graph_type"],
            "kwargs": {key: repr(value) for key, value in case["kwargs"].items()},
            "fnx": _serialize_result(fnx, fnx_graph, case["kwargs"]),
            "nx": _serialize_result(nx, nx_graph, case["kwargs"]),
        }
        record["matches_networkx"] = record["fnx"] == record["nx"]
        print(json.dumps(record, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
