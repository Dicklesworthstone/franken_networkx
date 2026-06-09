#!/usr/bin/env python3
"""Benchmark and proof harness for br-r37-c1-0e9ey edge attr exporters."""

from __future__ import annotations

import argparse
import cProfile
import hashlib
import json
import math
import pstats
import statistics
import tempfile
import time
from pathlib import Path

import franken_networkx as fnx
import networkx as nx


def available_ops():
    ops = ["adjacency_data", "node_link_data", "edges_data"]
    try:
        import pandas  # noqa: F401
    except ModuleNotFoundError:
        return ops
    ops.append("to_pandas_edgelist")
    return ops


def build_graph(lib, nodes: int, fanout: int, *, directed: bool):
    graph_cls = lib.DiGraph if directed else lib.Graph
    graph = graph_cls()
    graph.add_nodes_from(range(nodes))
    if directed:
        for u in range(nodes):
            for step in range(1, fanout + 1):
                v = (u + step * 37) % nodes
                if v == u:
                    continue
                graph.add_edge(
                    u,
                    v,
                    weight=(u * 131 + v * 17 + step) % 997,
                    capacity=(u + v + step) % 31,
                    label=f"e:{u}:{v}:{step}",
                )
    else:
        edges = []
        seen = set()
        for u in range(nodes):
            for step in range(1, fanout + 1):
                v = (u + step * 37) % nodes
                if v == u:
                    continue
                edge = (u, v) if u < v else (v, u)
                if edge in seen:
                    continue
                seen.add(edge)
                left, right = edge
                edges.append(
                    (
                        left,
                        right,
                        {
                            "weight": (left * 131 + right * 17 + step) % 997,
                            "capacity": (left + right + step) % 31,
                            "label": f"e:{left}:{right}:{step}",
                        },
                    )
                )
        graph.add_edges_from(edges)
    return graph


def stable(obj):
    if isinstance(obj, float) and math.isnan(obj):
        return "NaN"
    if isinstance(obj, dict):
        return {str(key): stable(value) for key, value in obj.items()}
    if isinstance(obj, tuple):
        return [stable(value) for value in obj]
    if isinstance(obj, list):
        return [stable(value) for value in obj]
    return obj


def operation_payload(lib, graph, op: str):
    if op == "adjacency_data":
        return lib.adjacency_data(graph)
    if op == "node_link_data":
        return lib.node_link_data(graph, edges="edges")
    if op == "to_pandas_edgelist":
        frame = lib.to_pandas_edgelist(graph)
        return frame.to_dict(orient="list")
    if op == "edges_data":
        return list(graph.edges(data=True))
    raise ValueError(op)


def canonical_payload(lib_name: str, payload):
    if lib_name == "fnx":
        return stable(payload)
    return stable(payload)


def payload_sha(payload) -> str:
    text = json.dumps(canonical_payload("", payload), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def proof(out: Path, nodes: int, fanout: int) -> None:
    rows = []
    for directed in (False, True):
        for op in available_ops():
            fg = build_graph(fnx, nodes, fanout, directed=directed)
            ng = build_graph(nx, nodes, fanout, directed=directed)
            fp = operation_payload(fnx, fg, op)
            np = operation_payload(nx, ng, op)
            rows.append(
                {
                    "case": "digraph" if directed else "graph",
                    "operation": op,
                    "match": canonical_payload("fnx", fp) == canonical_payload("nx", np),
                    "fnx_sha256": payload_sha(fp),
                    "nx_sha256": payload_sha(np),
                }
            )

    identity_rows = []
    for directed in (False, True):
        fg = build_graph(fnx, 32, 3, directed=directed)
        ng = build_graph(nx, 32, 3, directed=directed)
        f_u, f_v, f_attrs = next(iter(fg.edges(data=True)))
        n_u, n_v, n_attrs = next(iter(ng.edges(data=True)))
        f_attrs["identity_probe"] = 7
        n_attrs["identity_probe"] = 7
        identity_rows.append(
            {
                "case": "digraph" if directed else "graph",
                "fnx_live_dict_identity": f_attrs is fg[f_u][f_v],
                "nx_live_dict_identity": n_attrs is ng[n_u][n_v],
                "fnx_mutation_visible": fg[f_u][f_v]["identity_probe"] == 7,
                "nx_mutation_visible": ng[n_u][n_v]["identity_probe"] == 7,
            }
        )

    payload = {
        "bead": "br-r37-c1-0e9ey",
        "nodes": nodes,
        "fanout": fanout,
        "skipped_ops": sorted(
            set(["adjacency_data", "node_link_data", "to_pandas_edgelist", "edges_data"])
            - set(available_ops())
        ),
        "rows": rows,
        "identity_rows": identity_rows,
        "all_match": all(row["match"] for row in rows)
        and all(row["fnx_live_dict_identity"] == row["nx_live_dict_identity"] for row in identity_rows)
        and all(row["fnx_mutation_visible"] == row["nx_mutation_visible"] for row in identity_rows),
        "isomorphism": {
            "ordering": "node insertion order, adjacency-row order, and G.edges() order are compared directly against genuine NetworkX payloads",
            "tie_breaking": "N/A; deterministic fixture has no algorithmic tie choice beyond insertion order",
            "floating_point": "integer-valued weights/capacities; pandas NaN normalization is available but not exercised by this full-attr fixture",
            "rng": "N/A; graph fixture is deterministic arithmetic",
        },
    }
    text = json.dumps(payload, sort_keys=True, indent=2)
    out.write_text(text + "\n", encoding="utf-8")
    print(hashlib.sha256((text + "\n").encode("utf-8")).hexdigest())
    if not payload["all_match"]:
        raise SystemExit("proof mismatch")


def time_call(lib_name: str, op: str, nodes: int, fanout: int, directed: bool, repeats: int):
    lib = fnx if lib_name == "fnx" else nx
    graph = build_graph(lib, nodes, fanout, directed=directed)
    samples = []
    checksum = None
    for _ in range(repeats):
        start = time.perf_counter()
        payload = operation_payload(lib, graph, op)
        samples.append(time.perf_counter() - start)
        checksum = payload_sha(payload)
    result = {
        "lib": lib_name,
        "operation": op,
        "case": "digraph" if directed else "graph",
        "nodes": nodes,
        "edges": graph.number_of_edges(),
        "fanout": fanout,
        "repeats": repeats,
        "min_s": min(samples),
        "median_s": statistics.median(samples),
        "mean_s": statistics.mean(samples),
        "sha256": checksum,
    }
    print(json.dumps(result, sort_keys=True))


def profile(out: Path, op: str, nodes: int, fanout: int, directed: bool, repeats: int) -> None:
    graph = build_graph(fnx, nodes, fanout, directed=directed)
    profiler = cProfile.Profile()
    profiler.enable()
    for _ in range(repeats):
        operation_payload(fnx, graph, op)
    profiler.disable()
    with tempfile.NamedTemporaryFile() as tmp:
        profiler.dump_stats(tmp.name)
        stats = pstats.Stats(tmp.name)
        stats.sort_stats("cumulative")
        with out.open("w", encoding="utf-8") as handle:
            stats.stream = handle
            stats.print_stats(80)


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)

    proof_parser = sub.add_parser("proof")
    proof_parser.add_argument("--out", type=Path, required=True)
    proof_parser.add_argument("--nodes", type=int, default=48)
    proof_parser.add_argument("--fanout", type=int, default=4)

    time_parser = sub.add_parser("time")
    time_parser.add_argument("--lib", choices=["fnx", "nx"], required=True)
    time_parser.add_argument("--op", choices=["adjacency_data", "node_link_data", "to_pandas_edgelist", "edges_data"], required=True)
    time_parser.add_argument("--nodes", type=int, default=3000)
    time_parser.add_argument("--fanout", type=int, default=4)
    time_parser.add_argument("--directed", action="store_true")
    time_parser.add_argument("--repeats", type=int, default=5)

    profile_parser = sub.add_parser("profile")
    profile_parser.add_argument("--out", type=Path, required=True)
    profile_parser.add_argument("--op", choices=["adjacency_data", "node_link_data", "to_pandas_edgelist", "edges_data"], required=True)
    profile_parser.add_argument("--nodes", type=int, default=3000)
    profile_parser.add_argument("--fanout", type=int, default=4)
    profile_parser.add_argument("--directed", action="store_true")
    profile_parser.add_argument("--repeats", type=int, default=3)

    args = parser.parse_args()
    if args.cmd == "proof":
        proof(args.out, args.nodes, args.fanout)
    elif args.cmd == "time":
        time_call(args.lib, args.op, args.nodes, args.fanout, args.directed, args.repeats)
    else:
        profile(args.out, args.op, args.nodes, args.fanout, args.directed, args.repeats)


if __name__ == "__main__":
    main()
