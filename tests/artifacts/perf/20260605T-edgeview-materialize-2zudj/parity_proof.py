from __future__ import annotations

import hashlib
import json

import franken_networkx as fnx
import networkx as nx


def _normalize(value):
    if isinstance(value, dict):
        return {
            repr(key): _normalize(value[key])
            for key in sorted(value, key=repr)
        }
    if isinstance(value, tuple):
        return [_normalize(item) for item in value]
    if isinstance(value, list):
        return [_normalize(item) for item in value]
    return repr(value)


def _edge_identity_flags(graph):
    flags = []
    for u, v, attrs in graph.edges(data=True):
        flags.append(attrs is graph[u][v])
    return flags


def _build(module, case):
    graph = module.Graph()
    if case == "empty":
        return graph
    if case == "weighted_path":
        graph.add_nodes_from(range(5))
        graph.add_edges_from(
            (i, i + 1, {"weight": i, "label": f"e{i}"})
            for i in range(4)
        )
        return graph
    if case == "self_loop":
        graph.add_edge(0, 0, weight=9)
        graph.add_edge(0, 1, weight=1)
        graph.add_edge(1, 2, weight=2)
        return graph
    if case == "mixed_labels":
        graph.add_edge("a", 1, weight=3, color="red")
        graph.add_edge(1, ("t", 2), weight=4)
        graph.add_edge(("t", 2), "z")
        return graph
    raise AssertionError(case)


def _snapshot(label, graph, nx_graph):
    record = {"case": label}
    for data in [False, True, None, "weight", "missing"]:
        view = graph.edges(data=data, default="DEFAULT")
        nx_view = nx_graph.edges(data=data, default="DEFAULT")
        record[f"len:{data!r}"] = [len(view), len(nx_view)]
        record[f"edges:{data!r}"] = [_normalize(list(view)), _normalize(list(nx_view))]
    record["identity:fnx"] = _edge_identity_flags(graph)
    record["identity:nx"] = _edge_identity_flags(nx_graph)
    return record


def main():
    records = []
    mismatches = []
    for case in ["empty", "weighted_path", "self_loop", "mixed_labels"]:
        graph = _build(fnx, case)
        nx_graph = _build(nx, case)
        records.append(_snapshot(case, graph, nx_graph))

    graph = _build(fnx, "weighted_path")
    nx_graph = _build(nx, "weighted_path")
    view = graph.edges(data=True)
    nx_view = nx_graph.edges(data=True)
    before = [len(view), len(nx_view), _normalize(list(view)), _normalize(list(nx_view))]
    graph.add_edge(5, 6, weight=99)
    nx_graph.add_edge(5, 6, weight=99)
    after = [len(view), len(nx_view), _normalize(list(view)), _normalize(list(nx_view))]
    records.append({"case": "live_after_capture", "before": before, "after": after})

    graph = _build(fnx, "weighted_path")
    nx_graph = _build(nx, "weighted_path")
    nbunch = [3, 1, 100]
    records.append(
        {
            "case": "nbunch_fallback",
            "len": [len(graph.edges(nbunch, data=True)), len(nx_graph.edges(nbunch, data=True))],
            "edges": [
                _normalize(list(graph.edges(nbunch, data=True))),
                _normalize(list(nx_graph.edges(nbunch, data=True))),
            ],
        }
    )

    for record in records:
        if record.get("case") == "live_after_capture":
            before = record["before"]
            after = record["after"]
            if before[0] != before[1] or before[2] != before[3]:
                mismatches.append(["live_before", before])
            if after[0] != after[1] or after[2] != after[3]:
                mismatches.append(["live_after", after])
            continue
        if record.get("case") == "nbunch_fallback":
            if record["len"][0] != record["len"][1] or record["edges"][0] != record["edges"][1]:
                mismatches.append(["nbunch_fallback", record])
            continue
        for key, value in record.items():
            if key.startswith("len:") or key.startswith("edges:") or key.startswith("identity:"):
                if key.startswith("identity:"):
                    continue
                if value[0] != value[1]:
                    mismatches.append([record["case"], key, value])
        if record["identity:fnx"] != record["identity:nx"]:
            mismatches.append([record["case"], "identity", record["identity:fnx"], record["identity:nx"]])

    payload = json.dumps(records, sort_keys=True, separators=(",", ":"))
    sha = hashlib.sha256(payload.encode()).hexdigest()
    print(json.dumps({"cases": len(records), "mismatches": mismatches, "sha256": sha}, sort_keys=True))
    if mismatches:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
