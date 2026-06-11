"""Proof for br-r37-c1-1s6cb: fnx.algorithms.centrality routes to fnx top-level.

Parity: fnx.algorithms.centrality.X(H) vs genuine nx.algorithms.centrality.X(Gnx)
  -> rounded-golden sha256 + max abs diff (inherits fnx top-level's parity).
Speedup: routed (fnx) vs the previous behavior (raw nx submodule on fnx views).
"""
import time, hashlib, json, sys, warnings
warnings.filterwarnings("ignore")
import franken_networkx as fnx
import networkx as nx
import networkx.algorithms.centrality as nxc
from franken_networkx.backend import _fnx_to_nx


def gsig(d):
    items = sorted(d.items(), key=lambda kv: str(kv[0]))
    return hashlib.sha256(repr([(str(k), round(float(v), 9)) for k, v in items]).encode()).hexdigest()


def bench(fn, r=5):
    fn(); b = 1e9
    for _ in range(r):
        t = time.perf_counter(); fn(); b = min(b, time.perf_counter() - t)
    return b * 1000


out = {"routing": {}, "parity": {}, "speedup": {}}

# routing identity (the correctness backbone: submodule fn IS the fnx top-level fn)
for name in ["betweenness_centrality", "closeness_centrality", "harmonic_centrality",
             "load_centrality", "degree_centrality", "subgraph_centrality",
             "eigenvector_centrality", "katz_centrality", "second_order_centrality"]:
    out["routing"][name] = (
        getattr(fnx.algorithms.centrality, name) is getattr(fnx, name)
    )

# parity + speedup across graph sizes
for n, p, seed in [(200, 0.05, 3), (400, 0.04, 7)]:
    G = nx.gnp_random_graph(n, p, seed=seed)
    H = fnx.Graph(); H.add_nodes_from(G.nodes()); H.add_edges_from(G.edges())
    Gnx = _fnx_to_nx(H)
    for name in ["betweenness_centrality", "load_centrality", "closeness_centrality",
                 "harmonic_centrality", "degree_centrality"]:
        routed = getattr(fnx.algorithms.centrality, name)
        raw = getattr(nxc, name)
        fr = routed(H); nr = raw(Gnx)
        md = max(abs(fr[k] - nr[k]) for k in fr)
        key = f"{name}_n{n}"
        out["parity"][key] = {
            "sha_fnx": gsig(fr), "sha_nx": gsig(nr),
            "sha_match": gsig(fr) == gsig(nr), "maxdiff": md,
        }
    # speedup only for the heavy ones (n=400)
    if n == 400:
        for name in ["betweenness_centrality", "load_centrality"]:
            routed = getattr(fnx.algorithms.centrality, name)
            raw = getattr(nxc, name)
            a = bench(lambda: routed(H)); b = bench(lambda: raw(H))
            out["speedup"][name] = {
                "routed_ms": round(a, 2), "before_raw_nx_ms": round(b, 2),
                "speedup": round(b / a, 1),
            }

print(json.dumps(out, indent=2))
with open(sys.argv[1] if len(sys.argv) > 1 else "/tmp/cent_proof.json", "w") as f:
    json.dump(out, f, indent=2)
