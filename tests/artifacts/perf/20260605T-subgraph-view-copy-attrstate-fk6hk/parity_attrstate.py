from __future__ import annotations

import hashlib
import json
import sys

import franken_networkx as fnx
import networkx as nx


def _edge_rows(graph):
    if graph.is_multigraph():
        return [
            (u, v, key, tuple(sorted(attrs.items())))
            for u, v, key, attrs in graph.edges(keys=True, data=True)
        ]
    return [
        (u, v, tuple(sorted(attrs.items())))
        for u, v, attrs in graph.edges(data=True)
    ]


def _snapshot(graph):
    return {
        "nodes": [
            (node, tuple(sorted(attrs.items())))
            for node, attrs in graph.nodes(data=True)
        ],
        "edges": _edge_rows(graph),
    }


def _build_pair(kind, nodes, edges):
    nx_type, fnx_type = kind
    gn = nx_type()
    gf = fnx_type()
    gn.add_nodes_from(nodes)
    gf.add_nodes_from(nodes)
    gn.add_edges_from(edges)
    gf.add_edges_from(edges)
    return gn, gf


def _case(name, kind, nodes, edges, keep):
    gn, gf = _build_pair(kind, nodes, edges)
    nx_copy = gn.subgraph(keep).copy()
    fnx_copy = gf.subgraph(keep).copy()
    nx_snapshot = _snapshot(nx_copy)
    fnx_snapshot = _snapshot(fnx_copy)
    if name == "exact-int-empty-attrs":
        fnx_copy.nodes[next(iter(keep))]["copy_only"] = "yes"
        copy_isolated = "copy_only" not in gf.nodes[next(iter(keep))]
    else:
        copy_isolated = True
    row = {
        "name": name,
        "kind": kind[0].__name__,
        "keep_order": list(keep),
        "nx_order": list(nx_copy.nodes()),
        "fnx_order": list(fnx_copy.nodes()),
        "nx_copy": nx_snapshot,
        "fnx_copy": fnx_snapshot,
        "copy_isolated": copy_isolated,
    }
    row["matches"] = (
        row["nx_order"] == row["fnx_order"]
        and row["nx_copy"] == row["fnx_copy"]
        and row["copy_isolated"]
    )
    return row


def main() -> None:
    rows = [
        _case(
            "exact-int-empty-attrs",
            (nx.Graph, fnx.Graph),
            [130, 1155, 7, 1032, 909, 1934, 16, 786],
            [
                (130, 7, {"weight": 1}),
                (7, 909, {"weight": 2}),
                (909, 16, {"weight": 3}),
                (1155, 786, {"weight": 4}),
                (1032, 1934, {"weight": 5}),
            ],
            {130, 7, 909, 16},
        ),
        _case(
            "non-exact-int-fallback",
            (nx.Graph, fnx.Graph),
            [True, 1 << 80, 3.0, "3", 9],
            [
                (True, 1 << 80, {"weight": 1}),
                (1 << 80, 3.0, {"weight": 2}),
                ("3", 9, {"weight": 3}),
            ],
            {True, 1 << 80, 3.0, "3", 9},
        ),
        _case(
            "digraph-fallback",
            (nx.DiGraph, fnx.DiGraph),
            [5, 4, 3, 2, 1],
            [
                (5, 4, {"weight": 1}),
                (4, 3, {"weight": 2}),
                (2, 1, {"weight": 3}),
            ],
            {5, 4, 3},
        ),
    ]
    payload = "\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n"
    digest = hashlib.sha256(payload.encode()).hexdigest()
    print(
        json.dumps(
            {
                "cases": len(rows),
                "mismatches": sum(not row["matches"] for row in rows),
                "sha256": digest,
            },
            sort_keys=True,
        )
    )
    if "--write-jsonl" in sys.argv:
        sys.stdout.write(payload)
    if any(not row["matches"] for row in rows):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
