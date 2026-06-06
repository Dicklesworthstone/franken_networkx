import argparse
import hashlib
import json
import random
import time

import networkx as nx
import franken_networkx as fnx


def build_pair(n, m, seed):
    rnd = random.Random(seed)
    edges = []
    for i in range(m):
        u = rnd.randrange(n)
        v = rnd.randrange(n)
        edges.append((u, v, {"w": i, "payload": [u, v]}))
    fnx_dg = fnx.DiGraph()
    nx_dg = nx.DiGraph()
    for g in (fnx_dg, nx_dg):
        g.graph["marker"] = ["source", n, m]
        g.add_node("isolated", payload=[seed])
        g.add_edges_from(edges)
    return fnx_dg, nx_dg


def canonical(graph):
    rows = {repr(node): [repr(nbr) for nbr in graph[node]] for node in graph}
    edge_data = [
        (repr(u), repr(v), sorted(data.items(), key=lambda item: repr(item[0])))
        for u, v, data in graph.edges(data=True)
    ]
    node_data = [
        (repr(node), sorted(data.items(), key=lambda item: repr(item[0])))
        for node, data in graph.nodes(data=True)
    ]
    return {
        "nodes": [repr(node) for node in graph],
        "node_data": node_data,
        "edges": edge_data,
        "rows": rows,
        "graph": sorted(graph.graph.items(), key=lambda item: repr(item[0])),
    }


def digest_payload(cases):
    blob = json.dumps(cases, sort_keys=True, default=repr).encode()
    return hashlib.sha256(blob).hexdigest()


def proof():
    cases = []
    for n, m, seed in [(0, 0, 1), (1, 0, 2), (4, 10, 3), (17, 80, 4), (64, 512, 5)]:
        fnx_dg, nx_dg = build_pair(n, m, seed)
        fnx_graph = fnx.Graph(fnx_dg, extra=["attr"])
        nx_graph = nx.Graph(nx_dg, extra=["attr"])
        assert canonical(fnx_graph) == canonical(nx_graph), (n, m, seed)
        fnx_graph.add_edge(999, 1000, changed=[1])
        assert 999 not in fnx_dg
        cases.append(canonical(nx_graph))
    print("GOLDEN_SHA256", digest_payload(cases))
    print("CASES", len(cases))


def best_time(fn, runs):
    best = float("inf")
    for _ in range(runs):
        start = time.perf_counter()
        fn()
        best = min(best, time.perf_counter() - start)
    return best


def bench():
    for n, m, seed in [(800, 3200, 11), (3000, 12000, 12)]:
        fnx_dg, nx_dg = build_pair(n, m, seed)
        fnx_s = best_time(lambda: fnx.Graph(fnx_dg), 9)
        nx_s = best_time(lambda: nx.Graph(nx_dg), 9)
        print(
            json.dumps(
                {
                    "case": f"graph_digraph_{n}_{m}",
                    "fnx_s": fnx_s,
                    "nx_s": nx_s,
                    "ratio": fnx_s / nx_s,
                    "size": [
                        fnx.Graph(fnx_dg).number_of_nodes(),
                        fnx.Graph(fnx_dg).number_of_edges(),
                    ],
                },
                sort_keys=True,
            )
        )


def profile():
    fnx_dg, _ = build_pair(3000, 12000, 12)
    for _ in range(100):
        fnx.Graph(fnx_dg)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["proof", "bench", "profile"])
    args = parser.parse_args()
    if args.mode == "proof":
        proof()
    elif args.mode == "bench":
        bench()
    else:
        profile()


if __name__ == "__main__":
    main()
