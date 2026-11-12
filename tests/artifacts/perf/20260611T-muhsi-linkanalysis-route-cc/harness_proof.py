"""Proof for br-r37-c1-muhsi (link_analysis routing)."""
import time, hashlib, json, sys, warnings
warnings.filterwarnings("ignore")
import numpy as np
import franken_networkx as fnx
import networkx as nx
import networkx.algorithms.link_analysis as nxla
from franken_networkx.backend import _fnx_to_nx


def gsig(obj):
    if isinstance(obj, dict):
        body = repr([(str(k), round(float(v), 10)) for k, v in sorted(obj.items(), key=lambda kv: str(kv[0]))])
    elif isinstance(obj, tuple):  # hits
        body = repr([gsig(x) for x in obj])
        return hashlib.sha256(body.encode()).hexdigest()
    else:  # matrix
        body = repr(np.round(np.asarray(obj), 10).tolist())
    return hashlib.sha256(body.encode()).hexdigest()


def bench(fn, r=6):
    fn(); b = 1e9
    for _ in range(r):
        t = time.perf_counter(); fn(); b = min(b, time.perf_counter() - t)
    return b * 1000


out = {"routing": {}, "parity": {}, "speedup": {}}
for name in ["pagerank", "hits", "google_matrix"]:
    out["routing"][name] = getattr(fnx.algorithms.link_analysis, name) is getattr(fnx, name)

for n, p, seed in [(500, 0.02, 7), (1000, 0.01, 3)]:
    G = nx.gnp_random_graph(n, p, seed=seed)
    H = fnx.Graph(); H.add_nodes_from(G.nodes()); H.add_edges_from(G.edges())
    Gnx = _fnx_to_nx(H)
    for name in ["pagerank", "hits", "google_matrix"]:
        routed = getattr(fnx.algorithms.link_analysis, name)
        fr = routed(H); nr = getattr(nxla, name)(Gnx)
        out["parity"][f"{name}_n{n}"] = {"sha_match": gsig(fr) == gsig(nr)}
    if n == 1000:
        for name in ["google_matrix", "pagerank"]:
            routed = getattr(fnx.algorithms.link_analysis, name)
            raw = getattr(nxla, name)  # previous submodule behavior
            a = bench(lambda: routed(H)); b = bench(lambda: raw(H))
            out["speedup"][name] = {"routed_ms": round(a, 3), "before_raw_nx_ms": round(b, 3), "speedup": round(b / a, 2)}

print(json.dumps(out, indent=2))
with open(sys.argv[1] if len(sys.argv) > 1 else "/tmp/la_proof.json", "w") as f:
    json.dump(out, f, indent=2)
