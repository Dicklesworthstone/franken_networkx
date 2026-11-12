from __future__ import annotations

import argparse
import hashlib
import json
import random
from collections.abc import Mapping

import franken_networkx as fnx
import networkx as nx
from franken_networkx.backend import _fnx_to_nx


def atom(value):
    return {
        "type": type(value).__name__,
        "module": type(value).__module__,
        "repr": repr(value),
    }


def attrs(value):
    if not isinstance(value, Mapping):
        return atom(value)
    return [(atom(k), atom(v)) for k, v in value.items()]


def snapshot(graph):
    rows = []
    for node in graph:
        row = graph.adj[node]
        rows.append(
            {
                "node": atom(node),
                "node_attrs": attrs(graph.nodes[node]),
                "adj": [(atom(nbr), attrs(row[nbr])) for nbr in row],
            }
        )
    payload = {
        "class": type(graph).__name__,
        "directed": graph.is_directed(),
        "multigraph": graph.is_multigraph(),
        "graph_attrs": attrs(graph.graph),
        "nodes": [atom(n) for n in graph],
        "rows": rows,
    }
    if graph.is_directed():
        payload["pred_rows"] = [
            {
                "node": atom(node),
                "pred": [
                    (atom(pred), attrs(graph.pred[node][pred])) for pred in graph.pred[node]
                ],
            }
            for node in graph
        ]
    return payload


def assert_same(label, converted, expected):
    got = snapshot(converted)
    want = snapshot(expected)
    if got != want:
        raise AssertionError(
            json.dumps({"label": label, "got": got, "want": want}, sort_keys=True)
        )
    return {"label": label, "snapshot": got}


def add_edge_pair(fg, ng, u, v, **kw):
    fg.add_edge(u, v, **kw)
    ng.add_edge(u, v, **kw)


def z6uka_cases():
    cases = []
    values = [
        (0, 1.0, 1),
        (0, True, 1),
        ("s", 1.0, 1),
        ("s", 0.0, 0),
    ]
    for directed in (False, True):
        graph_type = fnx.DiGraph if directed else fnx.Graph
        nx_type = nx.DiGraph if directed else nx.Graph
        for idx, (source, stored, passed) in enumerate(values):
            fg, ng = graph_type(), nx_type()
            fg.add_node(source)
            ng.add_node(source)
            fg.add_node(stored)
            ng.add_node(stored)
            add_edge_pair(fg, ng, source, passed, weight=idx)
            cases.append((f"z6uka-{graph_type.__name__}-{idx}", fg, ng))

            fg2, ng2 = graph_type(), nx_type()
            fg2.add_node(source)
            ng2.add_node(source)
            fg2.add_node(stored)
            ng2.add_node(stored)
            add_edge_pair(fg2, ng2, passed, source, weight=idx)
            cases.append((f"z6uka-reversed-{graph_type.__name__}-{idx}", fg2, ng2))
    return cases


def structural_case(rng, index):
    directed = bool(index & 1)
    graph_type = fnx.DiGraph if directed else fnx.Graph
    nx_type = nx.DiGraph if directed else nx.Graph
    fg, ng = graph_type(), nx_type()
    n = rng.randrange(0, 18)
    nodes = list(range(n))
    rng.shuffle(nodes)
    for node in nodes:
        if rng.random() < 0.25:
            fg.add_node(node, label=f"n{node}", parity=node % 2)
            ng.add_node(node, label=f"n{node}", parity=node % 2)
        else:
            fg.add_node(node)
            ng.add_node(node)
    calls = rng.randrange(0, max(1, n * 3))
    for step in range(calls):
        if not nodes:
            break
        u = rng.choice(nodes)
        v = rng.choice(nodes)
        if rng.random() < 0.15:
            v = u
        if rng.random() < 0.35:
            add_edge_pair(fg, ng, u, v, weight=(u * 17 + v + step) % 19, tag=f"e{step}")
        else:
            add_edge_pair(fg, ng, u, v)
    fg.graph["seed"] = index
    ng.graph["seed"] = index
    return f"structural-{index}", fg, ng


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--structural", type=int, default=2500)
    parser.add_argument("--z6uka-repeat", type=int, default=100)
    args = parser.parse_args()

    rng = random.Random(0xF5A2)
    records = []

    base_z6uka = z6uka_cases()
    for repeat in range(args.z6uka_repeat):
        for label, fg, ng in base_z6uka:
            records.append(assert_same(f"{label}-r{repeat}", _fnx_to_nx(fg), ng))

    for index in range(args.structural):
        label, fg, ng = structural_case(rng, index)
        records.append(assert_same(label, _fnx_to_nx(fg), ng))

    lines = [json.dumps(record, sort_keys=True) for record in records]
    digest = hashlib.sha256(("\n".join(lines) + "\n").encode()).hexdigest()
    print(
        json.dumps(
            {
                "cases": len(records),
                "structural_cases": args.structural,
                "z6uka_cases": len(base_z6uka) * args.z6uka_repeat,
                "sha256": digest,
                "ordering": "converted node, adj, and directed pred row order exactly equals same-call NetworkX",
                "tie_breaking": "row order and row display objects preserve traversal tie-break inputs",
                "floating_point": "N/A: proof records attributes by repr/type; no arithmetic performed",
                "rng": "fixed local Random seed 0xF5A2 for structural case generation",
                "mixed_hash_equal": "{0, 1.0}, {0, True}, and reversed edge insertion z6uka cases included",
            },
            sort_keys=True,
        )
    )
    for line in lines:
        print(line)


if __name__ == "__main__":
    main()
