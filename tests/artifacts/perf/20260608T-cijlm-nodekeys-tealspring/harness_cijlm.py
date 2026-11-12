#!/usr/bin/env python3
import argparse
import hashlib
import json
import time

import franken_networkx as fnx
import networkx as nx


CASES = ("digraph", "multidigraph")


def graph_class(module, case):
    if case == "digraph":
        return module.DiGraph
    if case == "multidigraph":
        return module.MultiDiGraph
    raise ValueError(case)


def build_graph(module, case, n, fanout):
    graph = graph_class(module, case)()
    graph.add_nodes_from(range(n))
    for u in range(n):
        for step in range(1, fanout + 1):
            v = (u * 37 + step * 97) % n
            if v == u:
                v = (v + 1) % n
            graph.add_edge(u, v)
    return graph


def consume_non_neighbors(module, graph, nodes, calls):
    total = 0
    for i in range(calls):
        node = nodes[i % len(nodes)]
        total += sum(1 for _ in module.non_neighbors(graph, node))
    return total


def bench_one(module, case, n, fanout, calls):
    graph = build_graph(module, case, n, fanout)
    nodes = tuple(range(min(n, 256)))
    start = time.perf_counter()
    total = consume_non_neighbors(module, graph, nodes, calls)
    elapsed = time.perf_counter() - start
    return {
        "case": case,
        "nodes": n,
        "fanout": fanout,
        "calls": calls,
        "total": total,
        "seconds": elapsed,
    }


def direct(args):
    rows = []
    for case in CASES:
        fnx_row = bench_one(fnx, case, args.nodes, args.fanout, args.calls)
        nx_row = bench_one(nx, case, args.nodes, args.fanout, args.calls)
        rows.append(
            {
                "case": case,
                "fnx_seconds": fnx_row["seconds"],
                "nx_seconds": nx_row["seconds"],
                "ratio_fnx_to_nx": fnx_row["seconds"] / nx_row["seconds"],
                "fnx_total": fnx_row["total"],
                "nx_total": nx_row["total"],
            }
        )
    print(json.dumps({"rows": rows}, indent=2, sort_keys=True))


def hyperfine(args):
    module = fnx if args.library == "fnx" else nx
    row = bench_one(module, args.case, args.nodes, args.fanout, args.calls)
    print(json.dumps(row, sort_keys=True))


def proof(args):
    payload = {}
    mismatches = []
    for case in CASES:
        fnx_graph = build_graph(fnx, case, args.proof_nodes, args.fanout)
        nx_graph = build_graph(nx, case, args.proof_nodes, args.fanout)
        case_payload = {}
        for node in (0, 1, args.proof_nodes // 2, args.proof_nodes - 1):
            fnx_values = list(fnx.non_neighbors(fnx_graph, node))
            nx_values = list(nx.non_neighbors(nx_graph, node))
            case_payload[str(node)] = {
                "fnx": fnx_values,
                "nx": nx_values,
            }
            if fnx_values != nx_values:
                mismatches.append(
                    {
                        "case": case,
                        "node": node,
                        "fnx": fnx_values[:16],
                        "nx": nx_values[:16],
                    }
                )
        payload[case] = case_payload
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    print(
        json.dumps(
            {
                "sha256": hashlib.sha256(encoded).hexdigest(),
                "exact_equal": not mismatches,
                "mismatches": mismatches,
                "payload": payload,
            },
            indent=2,
            sort_keys=True,
        )
    )


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)

    direct_parser = sub.add_parser("direct")
    direct_parser.add_argument("--nodes", type=int, default=2000)
    direct_parser.add_argument("--fanout", type=int, default=3)
    direct_parser.add_argument("--calls", type=int, default=64)
    direct_parser.set_defaults(func=direct)

    hyperfine_parser = sub.add_parser("hyperfine")
    hyperfine_parser.add_argument("--library", choices=("fnx", "nx"), required=True)
    hyperfine_parser.add_argument("--case", choices=CASES, required=True)
    hyperfine_parser.add_argument("--nodes", type=int, default=2000)
    hyperfine_parser.add_argument("--fanout", type=int, default=3)
    hyperfine_parser.add_argument("--calls", type=int, default=64)
    hyperfine_parser.set_defaults(func=hyperfine)

    proof_parser = sub.add_parser("proof")
    proof_parser.add_argument("--proof-nodes", type=int, default=128)
    proof_parser.add_argument("--fanout", type=int, default=3)
    proof_parser.set_defaults(func=proof)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
