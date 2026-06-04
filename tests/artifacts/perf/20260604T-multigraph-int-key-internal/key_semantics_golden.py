#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from typing import Any

import franken_networkx as fnx
import networkx as nx


def token(value: Any) -> str:
    return f"{type(value).__name__}:{value!r}"


def edge_rows(graph: Any) -> list[list[Any]]:
    rows = []
    for u, v, key, data in graph.edges(keys=True, data=True):
        rows.append(
            [
                token(u),
                token(v),
                token(key),
                sorted((str(k), repr(vv)) for k, vv in data.items()),
            ]
        )
    return rows


def edge_data_rows(graph: Any, u: Any, v: Any) -> list[list[Any]]:
    data = graph.get_edge_data(u, v)
    if data is None:
        return []
    return [
        [token(key), sorted((str(k), repr(vv)) for k, vv in attrs.items())]
        for key, attrs in data.items()
    ]


def snapshot(module: Any) -> dict[str, Any]:
    cases: dict[str, Any] = {}

    graph = module.MultiGraph()
    first = graph.add_edge(1, 2, key=42)
    second = graph.add_edge(1, 2)
    cases["positive_then_auto"] = {
        "returns": [token(first), token(second)],
        "edges": edge_rows(graph),
        "edge_data": edge_data_rows(graph, 1, 2),
    }

    graph = module.MultiGraph()
    first = graph.add_edge(1, 2, key=-7)
    second = graph.add_edge(1, 2)
    cases["negative_then_auto"] = {
        "returns": [token(first), token(second)],
        "edges": edge_rows(graph),
        "edge_data": edge_data_rows(graph, 1, 2),
    }

    graph = module.MultiGraph()
    large_key = 10**30
    first = graph.add_edge(1, 2, key=large_key)
    second = graph.add_edge(1, 2)
    cases["large_then_auto"] = {
        "returns": [token(first), token(second)],
        "edges": edge_rows(graph),
        "edge_data": edge_data_rows(graph, 1, 2),
    }

    graph = module.MultiGraph()
    first = graph.add_edge(1, 2, key=5)
    second = graph.add_edge(1, 2, key=5, weight=3)
    cases["duplicate_key_update"] = {
        "returns": [token(first), token(second)],
        "edges": edge_rows(graph),
        "edge_data": edge_data_rows(graph, 1, 2),
    }

    graph = module.MultiGraph()
    for i in range(8):
        graph.add_edge(i, i + 1, key=i)
    cases["path_keys"] = {
        "edges": edge_rows(graph),
        "edge_data_3_4": edge_data_rows(graph, 3, 4),
    }

    return cases


payload = {"fnx": snapshot(fnx), "nx": snapshot(nx)}
payload["match"] = payload["fnx"] == payload["nx"]
encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
payload["sha256"] = hashlib.sha256(encoded).hexdigest()
print(json.dumps(payload, sort_keys=True))
