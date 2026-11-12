"""metric_closure de-delegation probe.

Current fnx.approximation.metric_closure passes the fnx graph straight to
nx.approximation.metric_closure, so nx's all_pairs_dijkstra runs over fnx
graph accessors (the 2.4x tax). Candidate: convert fnx->nx ONCE via
_networkx_graph_for_parity, run nx's metric_closure on the native nx graph,
convert the result back. Byte-identical to nx-on-equivalent-graph by
construction.
"""
import sys
import time
import json
import hashlib

import networkx as nx
import networkx.algorithms.approximation as nxa
import franken_networkx as fnx
import franken_networkx.approximation as fa


def make_pair(n, k, p, seed):
    g = nx.connected_watts_strogatz_graph(n, k, p, seed=seed)
    for u, v in g.edges():
        g.edges[u, v]["weight"] = float(1 + ((u * 7 + v * 13) % 5))
    fg = fnx.Graph()
    fg.add_nodes_from(g.nodes())
    for u, v, d in g.edges(data=True):
        fg.add_edge(u, v, weight=d["weight"])
    return fg, g


def candidate(G, weight="weight"):
    graph = fnx._networkx_graph_for_parity(G)
    nx_result = nxa.metric_closure(graph, weight=weight)
    from franken_networkx.readwrite import _from_nx_graph
    return _from_nx_graph(nx_result)


def edges_signature(M):
    rows = []
    for u, v in M.edges():
        d = M.edges[u, v]
        rows.append((u, v, d.get("distance"), tuple(d.get("path"))))
    rows.sort()
    return rows


def sha(obj):
    return hashlib.sha256(
        json.dumps(obj, sort_keys=True, default=list).encode()
    ).hexdigest()


def timeit(fn, G, reps):
    best = float("inf")
    for _ in range(reps):
        t0 = time.perf_counter()
        fn(G)
        dt = time.perf_counter() - t0
        best = min(best, dt)
    return best


def main():
    out = {}
    for (n, k, p) in [(150, 6, 0.1), (300, 6, 0.1)]:
        fg, g = make_pair(n, k, p, seed=42)

        cur = fa.metric_closure(fg)
        cand = candidate(fg)
        ref = nxa.metric_closure(g)

        cur_sig = edges_signature(cur)
        cand_sig = edges_signature(cand)
        ref_sig = edges_signature(ref)

        reps = 15
        t_cur = timeit(lambda G: fa.metric_closure(G), fg, reps)
        t_cand = timeit(lambda G: candidate(G), fg, reps)
        t_ref = timeit(lambda G: nxa.metric_closure(G), g, reps)

        key = f"ws{n}"
        out[key] = {
            "n": n,
            "cur_ms": t_cur * 1e3,
            "cand_ms": t_cand * 1e3,
            "nx_ms": t_ref * 1e3,
            "cur_vs_nx": t_ref / t_cur,
            "cand_vs_nx": t_ref / t_cand,
            "cand_vs_cur_speedup": t_cur / t_cand,
            "parity_cur_eq_nx": cur_sig == ref_sig,
            "parity_cand_eq_nx": cand_sig == ref_sig,
            "parity_cand_eq_cur": cand_sig == cur_sig,
            "sha_cur": sha(cur_sig),
            "sha_cand": sha(cand_sig),
            "sha_nx": sha(ref_sig),
        }
        print(json.dumps({key: out[key]}, indent=2, default=str))
    with open(sys.argv[1] if len(sys.argv) > 1 else "/tmp/mc.json", "w") as f:
        json.dump(out, f, indent=2, default=str)


if __name__ == "__main__":
    main()
