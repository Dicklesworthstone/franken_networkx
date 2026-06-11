"""Proof for br-r37-c1-eg2bz: approximation.large_clique_size de-delegation.
Parity vs genuine nx (incl. set-order tie-breaks + directed/multigraph raise);
speedup vs the previous delegated (_fnx_to_nx) path and vs genuine nx."""
import time, json, sys, warnings
warnings.filterwarnings("ignore")
import franken_networkx as fnx
import networkx as nx
import networkx.algorithms.approximation as napx
from franken_networkx.backend import _fnx_to_nx


def bench(fn, r=7):
    fn(); b = 1e9
    for _ in range(r):
        t = time.perf_counter(); fn(); b = min(b, time.perf_counter() - t)
    return b * 1000


out = {"parity": {}, "raise": {}, "speedup": {}}

# parity over adversarial graphs (wide degree ranges stress max(U,key=deg) ties)
gens = [("gnp_dense", lambda s: nx.gnp_random_graph(60, 0.2, seed=s)),
        ("ba", lambda s: nx.barabasi_albert_graph(70, 4, seed=s)),
        ("gnp_verydense", lambda s: nx.gnp_random_graph(40, 0.35, seed=s)),
        ("watts", lambda s: nx.watts_strogatz_graph(60, 6, 0.2, seed=s)),
        ("powerlaw", lambda s: nx.powerlaw_cluster_graph(80, 3, 0.3, seed=s))]
fails = 0; checks = 0
for s in range(60):
    for _, gen in gens:
        G = gen(s); H = fnx.Graph(); H.add_nodes_from(G.nodes()); H.add_edges_from(G.edges())
        Gnx = _fnx_to_nx(H)
        if fnx.approximation.large_clique_size(H) != napx.large_clique_size(Gnx):
            fails += 1
        checks += 1
# string-keyed
for s in range(20):
    base = nx.gnp_random_graph(50, 0.2, seed=s)
    G = nx.relabel_nodes(base, {i: f"n{i}" for i in base})
    H = fnx.Graph(); H.add_nodes_from(G.nodes()); H.add_edges_from(G.edges()); Gnx = _fnx_to_nx(H)
    if fnx.approximation.large_clique_size(H) != napx.large_clique_size(Gnx):
        fails += 1
    checks += 1
out["parity"] = {"checks": checks, "fails": fails}


def err(fn):
    try:
        fn(); return None
    except Exception as e:
        return type(e).__name__
GD = fnx.DiGraph([(0, 1), (1, 2)]); GDn = nx.DiGraph([(0, 1), (1, 2)])
MG = fnx.MultiGraph([(0, 1), (0, 1)]); MGn = nx.MultiGraph([(0, 1), (0, 1)])
out["raise"] = {"directed": [err(lambda: fnx.approximation.large_clique_size(GD)), err(lambda: napx.large_clique_size(GDn))],
                "multigraph": [err(lambda: fnx.approximation.large_clique_size(MG)), err(lambda: napx.large_clique_size(MGn))]}

# speedup
for n, p in [(300, 0.05), (600, 0.04), (1000, 0.03)]:
    G = nx.gnp_random_graph(n, p, seed=7); H = fnx.Graph(); H.add_nodes_from(G.nodes()); H.add_edges_from(G.edges()); Gnx = _fnx_to_nx(H)
    new = bench(lambda: fnx.approximation.large_clique_size(H))
    old = bench(lambda: napx.large_clique_size(_fnx_to_nx(H)))  # previous delegated path: convert + nx
    genuine = bench(lambda: napx.large_clique_size(Gnx))
    out["speedup"][f"n{n}"] = {"new_ms": round(new, 2), "delegated_ms": round(old, 2), "genuine_nx_ms": round(genuine, 2),
                              "vs_delegated": round(old / new, 2), "vs_nx": round(genuine / new, 2)}

print(json.dumps(out, indent=2))
with open(sys.argv[1] if len(sys.argv) > 1 else "/tmp/lcs.json", "w") as f:
    json.dump(out, f, indent=2)
