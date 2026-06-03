#!/usr/bin/env python3
"""Benchmark and golden harness for MultiGraph conversion copies."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import time

import franken_networkx as fnx
import networkx as nx


def _make_multigraph(module, n: int, edges: int, seed: int):
    rng = random.Random(seed)
    graph = module.MultiGraph()
    graph.graph["payload"] = {"tag": "mg", "items": [1, 2, 3]}
    for node in range(n):
        graph.add_node(node, payload={"node": node, "items": [node, node + 1]})
    for idx in range(edges):
        u = rng.randrange(n)
        v = rng.randrange(n)
        key = idx % 7
        graph.add_edge(
            u,
            v,
            key=key,
            weight=float((idx % 17) + 1) / 3.0,
            payload={"edge": idx, "items": [u, v, key]},
        )
    return graph


def _make_multidigraph(module, n: int, edges: int, seed: int):
    rng = random.Random(seed)
    graph = module.MultiDiGraph()
    graph.graph["payload"] = {"tag": "mdg", "items": [4, 5, 6]}
    for node in range(n):
        graph.add_node(node, payload={"node": node, "items": [node + 2]})
    for idx in range(edges):
        u = rng.randrange(n)
        v = rng.randrange(n)
        key = idx % 5
        graph.add_edge(
            u,
            v,
            key=key,
            weight=float((idx % 19) + 1) / 5.0,
            payload={"edge": idx, "items": [u, v, key]},
        )
    return graph


def _edge_rows(graph):
    rows = []
    for u, v, key, attrs in graph.edges(keys=True, data=True):
        rows.append([u, v, key, dict(attrs)])
    return rows


def _node_rows(graph):
    return [[node, dict(attrs)] for node, attrs in graph.nodes(data=True)]


def _normalize(graph):
    return {
        "type": type(graph).__name__,
        "directed": graph.is_directed(),
        "multigraph": graph.is_multigraph(),
        "graph": dict(graph.graph),
        "nodes": _node_rows(graph),
        "edges": _edge_rows(graph),
    }


def _first_edge_payload(graph):
    u, v, key, _attrs = next(iter(graph.edges(keys=True, data=True)))
    return graph[u][v][key]["payload"]


def _deepcopy_flags(source, converted):
    first_node = next(iter(source.nodes))
    return {
        "graph_payload_independent": converted.graph["payload"] is not source.graph["payload"],
        "node_payload_independent": (
            converted.nodes[first_node]["payload"] is not source.nodes[first_node]["payload"]
        ),
        "edge_payload_independent": (
            _first_edge_payload(converted) is not _first_edge_payload(source)
        ),
    }


def _converted(module, op: str, n: int, edges: int, seed: int):
    if op.startswith("mg_"):
        graph = _make_multigraph(module, n, edges, seed)
    else:
        graph = _make_multidigraph(module, n, edges, seed)
    if op.endswith("to_directed"):
        converted = graph.to_directed()
    else:
        converted = graph.to_undirected()
    return graph, converted


def golden(args) -> None:
    payload = {}
    for op in ("mg_to_directed", "mg_to_undirected", "mdg_to_directed", "mdg_to_undirected"):
        fnx_source, fnx_converted = _converted(fnx, op, args.nodes, args.edges, args.seed)
        nx_source, nx_converted = _converted(nx, op, args.nodes, args.edges, args.seed)
        fnx_norm = _normalize(fnx_converted)
        nx_norm = _normalize(nx_converted)
        payload[op] = {
            "fnx": fnx_norm,
            "nx": nx_norm,
            "matches_networkx": fnx_norm == nx_norm,
            "fnx_deepcopy": _deepcopy_flags(fnx_source, fnx_converted),
            "nx_deepcopy": _deepcopy_flags(nx_source, nx_converted),
        }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    print(hashlib.sha256(encoded).hexdigest())
    print(json.dumps(payload, sort_keys=True, indent=2))


def bench(args) -> None:
    module = fnx if args.impl == "fnx" else nx
    started = time.perf_counter()
    checksum = 0
    for idx in range(args.repeat):
        _source, converted = _converted(module, args.op, args.nodes, args.edges, args.seed + idx)
        checksum += converted.number_of_nodes()
        checksum += converted.number_of_edges()
    elapsed = time.perf_counter() - started
    result = {
        "impl": args.impl,
        "op": args.op,
        "nodes": args.nodes,
        "edges": args.edges,
        "repeat": args.repeat,
        "elapsed_s": elapsed,
        "per_iter_s": elapsed / args.repeat,
        "checksum": checksum,
    }
    print(json.dumps(result, sort_keys=True))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("bench", "golden"), required=True)
    parser.add_argument("--impl", choices=("fnx", "nx"), default="fnx")
    parser.add_argument(
        "--op",
        choices=("mg_to_directed", "mg_to_undirected", "mdg_to_directed", "mdg_to_undirected"),
        default="mg_to_directed",
    )
    parser.add_argument("--nodes", type=int, default=160)
    parser.add_argument("--edges", type=int, default=800)
    parser.add_argument("--repeat", type=int, default=5)
    parser.add_argument("--seed", type=int, default=20260603)
    args = parser.parse_args()
    if args.mode == "golden":
        golden(args)
    else:
        bench(args)


if __name__ == "__main__":
    main()
