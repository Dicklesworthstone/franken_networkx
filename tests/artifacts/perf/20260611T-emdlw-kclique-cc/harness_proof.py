"""Before/after proof for br-r37-c1-emdlw k_clique_communities."""
import time, hashlib, json, sys
import franken_networkx as fnx
import networkx as nx
from franken_networkx.backend import _fnx_to_nx
import networkx.algorithms.community as nxc


def to_fnx(G):
    H = fnx.Graph(); H.add_nodes_from(G.nodes()); H.add_edges_from(G.edges()); return H


def sig(c):
    return hashlib.sha256("\n".join(
        ",".join(map(str, sorted(s, key=lambda x: (str(type(x)), x)))) for s in c
    ).encode()).hexdigest()


def bench(fn, reps=7, inner=2):
    best = []
    for _ in range(reps):
        ts = []
        for _ in range(inner):
            t0 = time.perf_counter(); fn(); ts.append(time.perf_counter() - t0)
        best.append(min(ts))
    return min(best)


out = {}
for n, p, k, seed in [(300, 0.04, 3, 3), (500, 0.05, 3, 9),
                      (150, 0.25, 3, 4), (120, 0.35, 3, 4), (80, 0.5, 3, 4)]:
    G = nx.gnp_random_graph(n, p, seed=seed)
    H = to_fnx(G); Gnx = _fnx_to_nx(H)
    after_fn = lambda: list(fnx.community.k_clique_communities(H, k))
    before_fn = lambda: list(nxc.k_clique_communities(H, k))   # dispatch+convert path
    nx_fn = lambda: list(nxc.k_clique_communities(Gnx, k))
    sa, sb, sn = sig(after_fn()), sig(before_fn()), sig(nx_fn())
    b, a, nn = bench(before_fn), bench(after_fn), bench(nx_fn)
    rec = {
        "density": p, "before_ms": round(b * 1000, 3), "after_ms": round(a * 1000, 3),
        "nx_ms": round(nn * 1000, 3), "self_speedup": round(b / a, 3),
        "after_vs_nx": round(a / nn, 3),
        "sha_after": sa, "sha_before": sb, "sha_nx": sn,
        "sha_match": sa == sb == sn,
    }
    out[f"n{n}_p{p}_k{k}"] = rec
    print(json.dumps({f"n{n}_p{p}_k{k}": rec}, indent=2))

with open(sys.argv[1] if len(sys.argv) > 1 else "/tmp/kclique_proof.json", "w") as f:
    json.dump(out, f, indent=2)
