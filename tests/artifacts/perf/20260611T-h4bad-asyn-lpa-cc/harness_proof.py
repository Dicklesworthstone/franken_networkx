"""Before/after proof for br-r37-c1-h4bad asyn_lpa_communities.

BEFORE = nx's pure-Python asyn_lpa run on the fnx Graph (what the
``from networkx... import *`` re-export did).
AFTER  = the fnx-native index-space mark-array implementation.
nx      = nx run on the converted (same-adjacency) nx graph.
Golden sha256 over the order-sensitive community stream proves byte parity.
"""
import time, hashlib, json, sys, random
import franken_networkx as fnx
import networkx as nx
from franken_networkx.backend import _fnx_to_nx
import networkx.algorithms.community as nxc


def to_fnx(G):
    H = fnx.Graph()
    H.add_nodes_from(G.nodes())
    H.add_edges_from((u, v, dict(d)) for u, v, d in G.edges(data=True))
    return H


def sig(communities):
    parts = [",".join(map(str, sorted(s, key=lambda x: (str(type(x)), x))))
             for s in communities]
    return hashlib.sha256("\n".join(parts).encode()).hexdigest()


def bench(fn, reps=9, inner=3):
    best = []
    for _ in range(reps):
        ts = []
        for _ in range(inner):
            t0 = time.perf_counter(); fn(); ts.append(time.perf_counter() - t0)
        best.append(min(ts))
    return min(best)


out = {}
for n, p, seed in [(400, 0.05, 42), (800, 0.03, 11), (1500, 0.02, 5)]:
    G = nx.gnp_random_graph(n, p, seed=seed)
    H = to_fnx(G)
    Gnx = _fnx_to_nx(H)

    after_fn = lambda: list(fnx.community.asyn_lpa_communities(H, seed=seed))
    before_fn = lambda: list(nxc.asyn_lpa_communities(H, seed=seed))   # nx on fnx graph
    nx_fn = lambda: list(nxc.asyn_lpa_communities(Gnx, seed=seed))

    sa, sb, sn = sig(after_fn()), sig(before_fn()), sig(nx_fn())
    b = bench(before_fn); a = bench(after_fn); nn = bench(nx_fn)
    rec = {
        "before_ms": round(b * 1000, 3), "after_ms": round(a * 1000, 3),
        "nx_ms": round(nn * 1000, 3),
        "self_speedup": round(b / a, 3),
        "before_vs_nx": round(b / nn, 3), "after_vs_nx": round(a / nn, 3),
        "sha_after": sa, "sha_before": sb, "sha_nx": sn,
        "sha_match": sa == sb == sn,
    }
    out[f"n{n}_p{p}"] = rec
    print(json.dumps({f"n{n}_p{p}": rec}, indent=2))

with open(sys.argv[1] if len(sys.argv) > 1 else "/tmp/lpa_proof.json", "w") as f:
    json.dump(out, f, indent=2)
