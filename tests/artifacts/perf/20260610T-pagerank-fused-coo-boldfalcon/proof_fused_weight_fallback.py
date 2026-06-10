#!/usr/bin/env python3
"""Golden proof for fused PageRank weight validation + COO emission."""

from __future__ import annotations

import hashlib
import json
import math

import franken_networkx as fnx
import networkx as nx

try:
    from franken_networkx._fnx import pagerank_default_order_arrays_checked
except ImportError:
    pagerank_default_order_arrays_checked = None


def _graph_pair(graph_type, edges, *, mutate=None):
    fnx_graph = graph_type[0]()
    nx_graph = graph_type[1]()
    for graph in (fnx_graph, nx_graph):
        graph.add_nodes_from([0, 1, 2, 3])
        graph.add_edges_from(edges)
    if mutate is not None:
        u, v, value = mutate
        fnx_graph[u][v]["weight"] = value
        nx_graph[u][v]["weight"] = value
    return fnx_graph, nx_graph


def _canonical_value(value):
    if isinstance(value, float):
        if math.isnan(value):
            return "nan"
        if math.isinf(value):
            return "inf" if value > 0.0 else "-inf"
        return format(value, ".17g")
    return repr(value)


def _capture(call):
    try:
        result = call()
    except Exception as exc:  # noqa: BLE001 - proof records observable parity.
        return {
            "kind": "error",
            "type": type(exc).__name__,
            "message": str(exc),
        }
    return {
        "kind": "ok",
        "rows": [(node, _canonical_value(result[node])) for node in result],
    }


def main() -> None:
    cases = [
        (
            "finite_directed",
            (fnx.DiGraph, nx.DiGraph),
            [
                (0, 1, {"weight": 1.0}),
                (1, 2, {"weight": 2.0}),
                (2, 0, {}),
                (2, 3, {"weight": 0.5}),
            ],
            None,
        ),
        (
            "nan_directed",
            (fnx.DiGraph, nx.DiGraph),
            [(0, 1, {"weight": math.nan}), (1, 2, {"weight": 1.0})],
            None,
        ),
        (
            "inf_directed",
            (fnx.DiGraph, nx.DiGraph),
            [(0, 1, {"weight": math.inf}), (1, 2, {"weight": 1.0})],
            None,
        ),
        (
            "string_directed",
            (fnx.DiGraph, nx.DiGraph),
            [(0, 1, {"weight": "heavy"}), (1, 2, {"weight": 1.0})],
            None,
        ),
        (
            "dirty_inf_directed",
            (fnx.DiGraph, nx.DiGraph),
            [(0, 1, {"weight": 1.0}), (1, 2, {"weight": 1.0})],
            (0, 1, math.inf),
        ),
        (
            "finite_undirected",
            (fnx.Graph, nx.Graph),
            [
                (0, 1, {"weight": 1.0}),
                (1, 2, {"weight": 2.0}),
                (2, 0, {}),
                (2, 3, {"weight": 0.5}),
            ],
            None,
        ),
        (
            "nan_undirected",
            (fnx.Graph, nx.Graph),
            [(0, 1, {"weight": math.nan}), (1, 2, {"weight": 1.0})],
            None,
        ),
    ]

    rows = []
    for label, graph_type, edges, mutate in cases:
        fnx_graph, nx_graph = _graph_pair(graph_type, edges, mutate=mutate)
        fnx_result = _capture(
            lambda graph=fnx_graph: fnx.pagerank(
                graph, weight="weight", tol=1e-8, max_iter=100
            )
        )
        checked = (
            None
            if pagerank_default_order_arrays_checked is None
            else pagerank_default_order_arrays_checked(fnx_graph, "weight", 1.0)
        )
        nx_result = _capture(
            lambda graph=nx_graph: nx.pagerank(
                graph, weight="weight", tol=1e-8, max_iter=100
            )
        )
        rows.append(
            {
                "case": label,
                "helper_returned": checked is not None,
                "helper_has_nonfinite": None if checked is None else bool(checked[0]),
                "helper_edge_entries": None if checked is None else len(checked[1]),
                "fnx": fnx_result,
                "nx": nx_result,
                "matches_nx": fnx_result == nx_result,
            }
        )

    payload = {
        "cases": rows,
        "all_match": all(row["matches_nx"] for row in rows),
        "ordering": "PageRank result dict follows dict(zip(list(G), x)); list(G) is unchanged.",
        "tie_breaking": "No graph traversal tie-break policy changes; sparse matrix COO ordering is assembly-order independent.",
        "floating_point": "Finite cases use the same scipy sparse power iteration; nonfinite/nonnumeric cases delegate to NetworkX.",
        "rng": "None.",
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    payload["proof_sha256"] = hashlib.sha256(encoded.encode()).hexdigest()
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
