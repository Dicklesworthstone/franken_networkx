from __future__ import annotations

import hashlib
import json
import random
import sys

import franken_networkx as fnx
import networkx as nx


def _graph_pair(kind: str):
    if kind == "graph":
        return nx.Graph(), fnx.Graph()
    if kind == "digraph":
        return nx.DiGraph(), fnx.DiGraph()
    if kind == "multigraph":
        return nx.MultiGraph(), fnx.MultiGraph()
    if kind == "multidigraph":
        return nx.MultiDiGraph(), fnx.MultiDiGraph()
    raise AssertionError(kind)


def _add_edge(graph, u, v, key, attrs):
    if graph.is_multigraph():
        graph.add_edge(u, v, key=key, **attrs)
    else:
        graph.add_edge(u, v, **attrs)


def _build_pair(kind: str, seed: int, n: int):
    rng = random.Random(seed)
    gn, gf = _graph_pair(kind)
    insertion_order = list(range(n))
    rng.shuffle(insertion_order)
    gn.add_nodes_from((node, {"payload": node % 5}) for node in insertion_order)
    gf.add_nodes_from((node, {"payload": node % 5}) for node in insertion_order)
    for i in range(n * 3):
        u = insertion_order[(i * 17 + 3) % n]
        v = insertion_order[(i * 29 + 11) % n]
        if u == v:
            continue
        attrs = {"weight": (i % 7) + 1, "tag": f"e{i % 13}"}
        _add_edge(gn, u, v, i % 4, attrs)
        _add_edge(gf, u, v, i % 4, attrs)
    return gn, gf, insertion_order


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


def _case(kind: str, seed: int, n: int, keep_size: int):
    gn, gf, insertion_order = _build_pair(kind, seed, n)
    keep = set(insertion_order[:keep_size])
    nx_view = gn.subgraph(keep)
    fnx_view = gf.subgraph(keep)
    nx_copy = nx_view.copy()
    fnx_copy = fnx_view.copy()
    row = {
        "kind": kind,
        "seed": seed,
        "n": n,
        "keep_size": keep_size,
        "shortcut": 2 * keep_size < n,
        "nx_view_order": list(nx_view.nodes()),
        "fnx_view_order": list(fnx_view.nodes()),
        "nx_copy": _snapshot(nx_copy),
        "fnx_copy": _snapshot(fnx_copy),
    }
    row["matches"] = (
        row["nx_copy"] == row["fnx_copy"]
        and row["nx_view_order"] == row["fnx_view_order"]
    )
    return row


def main() -> None:
    rows = []
    mismatches = []
    for kind in ("graph", "digraph", "multigraph", "multidigraph"):
        for seed in range(24):
            for n, keep_size in ((12, 4), (80, 5), (2000, 50)):
                row = _case(kind, seed, n, keep_size)
                rows.append(row)
                if not row["matches"]:
                    mismatches.append(row)
    payload = "\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n"
    digest = hashlib.sha256(payload.encode()).hexdigest()
    print(json.dumps(
        {"cases": len(rows), "mismatches": len(mismatches), "sha256": digest},
        sort_keys=True,
    ))
    if "--write-jsonl" in sys.argv:
        sys.stdout.write(payload)
    if mismatches:
        first = mismatches[0]
        print(json.dumps({
            "first_mismatch": {
                "kind": first["kind"],
                "seed": first["seed"],
                "n": first["n"],
                "keep_size": first["keep_size"],
                "nx_order_head": first["nx_view_order"][:12],
                "fnx_order_head": first["fnx_view_order"][:12],
            },
        }, sort_keys=True), file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
