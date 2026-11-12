#!/usr/bin/env python3
"""Benchmark conversion-view construction with and without empty base storage."""

from __future__ import annotations

import argparse
import gc
import hashlib
import json
import statistics
import time


def _install_old_conversion_new(fnx_module):
    base = fnx_module._ConversionGraphViewBase

    def old_new(cls, graph=None, *args, **kwargs):
        return super(base, cls).__new__(cls, graph)

    base.__new__ = staticmethod(old_new)


def _edge_payload(graph):
    if graph.is_multigraph():
        return [
            [repr(u), repr(v), repr(k), sorted((str(a), repr(vv)) for a, vv in data.items())]
            for u, v, k, data in graph.edges(keys=True, data=True)
        ]
    return [
        [repr(u), repr(v), sorted((str(a), repr(vv)) for a, vv in data.items())]
        for u, v, data in graph.edges(data=True)
    ]


def _snapshot(view):
    nodes = [[repr(node), sorted((str(k), repr(v)) for k, v in attrs.items())]
             for node, attrs in view.nodes(data=True)]
    edges = _edge_payload(view)
    degrees = [[repr(node), degree] for node, degree in view.degree()]
    weighted_degrees = [[repr(node), degree] for node, degree in view.degree(weight="weight")]
    copied = view.copy()
    payload = {
        "type": type(view).__name__,
        "directed": view.is_directed(),
        "multigraph": view.is_multigraph(),
        "nodes": nodes,
        "edges": edges,
        "degree": degrees,
        "weighted_degree": weighted_degrees,
        "size": view.size(),
        "weighted_size": view.size(weight="weight"),
        "number_of_nodes": view.number_of_nodes(),
        "number_of_edges": view.number_of_edges(),
        "contains_0": 0 in view,
        "has_0_1": view.has_edge(0, 1),
        "copy_directed": copied.is_directed(),
        "copy_multigraph": copied.is_multigraph(),
        "copy_edges": _edge_payload(copied),
    }
    data = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(data).hexdigest()


def _build_edges(n, degree):
    for node in range(n):
        for offset in range(1, degree + 1):
            neighbor = node + offset
            if neighbor < n:
                yield node, neighbor, {"weight": (node * 131 + offset) % 17 + 1}


def _build_graph(module, graph_kind, n, degree):
    graph = getattr(module, graph_kind)()
    graph.add_nodes_from((node, {"label": f"n{node}"}) for node in range(n))
    edges = list(_build_edges(n, degree))
    if graph.is_multigraph():
        graph.add_edges_from((u, v, f"k{idx % 3}", data) for idx, (u, v, data) in enumerate(edges))
    else:
        graph.add_edges_from(edges)
    return graph


def _case_specs():
    return [
        ("graph_to_directed", "Graph", "to_directed"),
        ("digraph_to_undirected", "DiGraph", "to_undirected"),
        ("multigraph_to_directed", "MultiGraph", "to_directed"),
        ("multidigraph_to_undirected", "MultiDiGraph", "to_undirected"),
    ]


def _module_for_engine(engine):
    if engine == "nx":
        import networkx as module
    else:
        import franken_networkx as module
        if engine == "fnx-old":
            _install_old_conversion_new(module)
    return module


def run(engine, n, degree, calls, digest_n, case_filter):
    module = _module_for_engine(engine)
    cases = []
    for name, graph_kind, direction in _case_specs():
        if case_filter is not None and name != case_filter:
            continue
        graph = _build_graph(module, graph_kind, n, degree)
        small_graph = _build_graph(module, graph_kind, digest_n, degree)
        golden = getattr(small_graph, direction)(as_view=True)
        gc.collect()
        old_gc_state = gc.isenabled()
        gc.disable()
        start = time.perf_counter_ns()
        for _ in range(calls):
            view = getattr(graph, direction)(as_view=True)
            if view.number_of_nodes() != n:
                raise AssertionError("view construction returned wrong node count")
        elapsed = time.perf_counter_ns() - start
        if old_gc_state:
            gc.enable()
        per_call = elapsed / calls / 1_000_000_000
        cases.append(
            {
                "case": name,
                "seconds_per_call": per_call,
                "digest": _snapshot(golden),
            }
        )
    snapshot_cases = [
        {"case": case["case"], "digest": case["digest"]}
        for case in cases
    ]
    combined = hashlib.sha256(
        json.dumps(snapshot_cases, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return {
        "engine": engine,
        "n": n,
        "degree": degree,
        "calls": calls,
        "digest_n": digest_n,
        "mean_seconds_per_call": statistics.fmean(case["seconds_per_call"] for case in cases),
        "cases": cases,
        "combined_snapshot_digest": combined,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--engine", choices=["fnx-old", "fnx-new", "nx"], required=True)
    parser.add_argument("--n", type=int, default=8000)
    parser.add_argument("--degree", type=int, default=4)
    parser.add_argument("--calls", type=int, default=16)
    parser.add_argument("--digest-n", type=int, default=64)
    parser.add_argument(
        "--case",
        choices=[name for name, _, _ in _case_specs()],
        default=None,
    )
    args = parser.parse_args()
    print(
        json.dumps(
            run(args.engine, args.n, args.degree, args.calls, args.digest_n, args.case),
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
