#!/usr/bin/env python3
"""Benchmark and proof harness for br-r37-c1-jfsyo k_components."""

from __future__ import annotations

import argparse
import cProfile
import hashlib
import json
import pstats
import tempfile
import time
from pathlib import Path

import franken_networkx as fnx
import networkx as nx


def genuine_nx_k_components(graph, flow_func=None):
    func = getattr(nx.k_components, "orig_func", nx.k_components)
    return func(graph, flow_func=flow_func)


def canonical(result):
    return [
        {
            "k": k,
            "value_type": type(value).__name__,
            "components": [
                {
                    "type": type(component).__name__,
                    "nodes": sorted(repr(node) for node in component),
                }
                for component in value
            ],
        }
        for k, value in result.items()
    ]


def fnx_complete_multipartite(*sizes):
    graph = fnx.Graph()
    offset = 0
    parts = []
    for size in sizes:
        part = list(range(offset, offset + size))
        graph.add_nodes_from(part)
        parts.append(part)
        offset += size
    for i, left in enumerate(parts):
        for right in parts[i + 1 :]:
            graph.add_edges_from((u, v) for u in left for v in right)
    return graph


def disjoint_union_families(lib):
    return disjoint_complete_multipartite(lib, (2, 3), (3, 4, 5))


def disjoint_complete_multipartite(lib, *families):
    graph = lib.Graph()
    offset = 0
    for sizes in families:
        if lib is nx:
            component = nx.complete_multipartite_graph(*sizes)
        else:
            component = fnx_complete_multipartite(*sizes)
        mapping = {node: node + offset for node in component.nodes()}
        graph.add_nodes_from(mapping.values())
        graph.add_edges_from((mapping[u], mapping[v]) for u, v in component.edges())
        offset += sum(sizes)
    return graph


def proof_cases():
    missing_cross_fnx = fnx_complete_multipartite(3, 4)
    missing_cross_nx = nx.complete_bipartite_graph(3, 4)
    missing_cross_fnx.remove_edge(0, 3)
    missing_cross_nx.remove_edge(0, 3)

    return [
        (
            "complete_bipartite_2_3",
            fnx_complete_multipartite(2, 3),
            nx.complete_bipartite_graph(2, 3),
        ),
        (
            "complete_bipartite_3_5",
            fnx_complete_multipartite(3, 5),
            nx.complete_bipartite_graph(3, 5),
        ),
        (
            "complete_multipartite_3_3_3",
            fnx_complete_multipartite(3, 3, 3),
            nx.complete_multipartite_graph(3, 3, 3),
        ),
        (
            "complete_multipartite_2_4_5",
            fnx_complete_multipartite(2, 4, 5),
            nx.complete_multipartite_graph(2, 4, 5),
        ),
        ("disjoint_complete_multipartite", disjoint_union_families(fnx), disjoint_union_families(nx)),
        (
            "disjoint_mixed_connectivity_order",
            disjoint_complete_multipartite(fnx, (2, 2, 2), (2, 3), (1, 2, 3)),
            disjoint_complete_multipartite(nx, (2, 2, 2), (2, 3), (1, 2, 3)),
        ),
        ("missing_cross_edge_delegates", missing_cross_fnx, missing_cross_nx),
    ]


def proof(out: Path) -> None:
    rows = []
    for name, f_graph, nx_graph in proof_cases():
        f_result = fnx.k_components(f_graph)
        nx_result = genuine_nx_k_components(nx_graph)
        rows.append(
            {
                "case": name,
                "fnx": canonical(f_result),
                "nx": canonical(nx_result),
                "match": canonical(f_result) == canonical(nx_result),
                "key_order": list(f_result.keys()),
            }
        )

    def fail_flow(*_args, **_kwargs):
        raise RuntimeError("flow called")

    flow_rows = []
    for name, f_graph, nx_graph in proof_cases()[:4]:
        f_exc = nx_exc = None
        try:
            fnx.k_components(f_graph, flow_func=fail_flow)
        except Exception as exc:  # noqa: BLE001 - proof records observable type/message.
            f_exc = [type(exc).__name__, str(exc)]
        try:
            genuine_nx_k_components(nx_graph, flow_func=fail_flow)
        except Exception as exc:  # noqa: BLE001 - proof records observable type/message.
            nx_exc = [type(exc).__name__, str(exc)]
        flow_rows.append({"case": name, "fnx": f_exc, "nx": nx_exc, "match": f_exc == nx_exc})

    payload = {
        "fnx_file": fnx.__file__,
        "nx_version": nx.__version__,
        "cases": rows,
        "flow_func_cases": flow_rows,
        "all_match": all(row["match"] for row in rows)
        and all(row["match"] for row in flow_rows),
        "isomorphism": {
            "ordering_preserved": (
                "keys descend from vertex-connectivity to 1; levels above 2 prepend exact-k "
                "components before carried higher-k components, while levels 2 and 1 use "
                "connected-component order, matching NetworkX reconstruction"
            ),
            "tie_breaking_unchanged": (
                "closed-form cases contain one maximal component per connected complete "
                "multipartite component at each k; non-matching graphs delegate"
            ),
            "floating_point": "N/A",
            "rng": "N/A",
        },
    }
    text = json.dumps(payload, sort_keys=True, indent=2)
    out.write_text(text + "\n", encoding="utf-8")
    print(hashlib.sha256((text + "\n").encode("utf-8")).hexdigest())
    if not payload["all_match"]:
        raise SystemExit("proof mismatch")


def make_graph(which: str, size: int):
    if which == "fnx":
        return fnx_complete_multipartite(size, size, size)
    if which == "nx":
        return nx.complete_multipartite_graph(size, size, size)
    raise ValueError(which)


def time_case(size: int, repeats: int, which: str) -> None:
    graph = make_graph(which, size)
    if which == "fnx":
        func = fnx.k_components
    else:
        func = genuine_nx_k_components

    start = time.perf_counter()
    result = None
    for _ in range(repeats):
        result = func(graph)
    elapsed = time.perf_counter() - start
    payload = {
        "which": which,
        "family": "complete_multipartite_equal3",
        "size_per_part": size,
        "nodes": graph.number_of_nodes(),
        "edges": graph.number_of_edges(),
        "repeats": repeats,
        "seconds": elapsed,
        "seconds_per_call": elapsed / repeats,
        "result_sha256": hashlib.sha256(
            json.dumps(canonical(result), sort_keys=True).encode("utf-8")
        ).hexdigest(),
    }
    print(json.dumps(payload, sort_keys=True))


def profile_case(size: int, repeats: int, out: Path) -> None:
    graph = make_graph("fnx", size)
    profiler = cProfile.Profile()
    profiler.enable()
    for _ in range(repeats):
        fnx.k_components(graph)
    profiler.disable()
    with tempfile.NamedTemporaryFile() as tmp:
        profiler.dump_stats(tmp.name)
        stats = pstats.Stats(tmp.name)
        stats.sort_stats("cumulative")
        with out.open("w", encoding="utf-8") as handle:
            stats.stream = handle
            stats.print_stats(60)


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)

    proof_parser = sub.add_parser("proof")
    proof_parser.add_argument("--out", type=Path, required=True)

    time_parser = sub.add_parser("time")
    time_parser.add_argument("--size", type=int, default=80)
    time_parser.add_argument("--repeats", type=int, default=1)
    time_parser.add_argument("--which", choices=["fnx", "nx"], default="fnx")

    profile_parser = sub.add_parser("profile")
    profile_parser.add_argument("--size", type=int, default=60)
    profile_parser.add_argument("--repeats", type=int, default=1)
    profile_parser.add_argument("--out", type=Path, required=True)

    args = parser.parse_args()
    if args.cmd == "proof":
        proof(args.out)
    elif args.cmd == "time":
        time_case(args.size, args.repeats, args.which)
    else:
        profile_case(args.size, args.repeats, args.out)


if __name__ == "__main__":
    main()
