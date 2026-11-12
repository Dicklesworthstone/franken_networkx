"""Proof: fnx.convert.to_dict_of_dicts routes to native fnx (~16x vs old
nx-on-views submodule path). Parity vs genuine nx incl nodelist/edge_data/digraph."""
import time, json, sys, warnings
warnings.filterwarnings("ignore")
import franken_networkx as fnx
import networkx as nx
import networkx.convert as nc
import franken_networkx.convert as fc
from franken_networkx.backend import _fnx_to_nx


def bench(fn, r=8):
    fn(); b = 1e9
    for _ in range(r):
        t = time.perf_counter(); fn(); b = min(b, time.perf_counter() - t)
    return b * 1000


out = {"routed": fc.to_dict_of_dicts is not nc.to_dict_of_dicts, "parity": {}, "speedup": {}}

# parity (default / weighted / nodelist / edge_data / digraph)
pf = 0
for s in range(80):
    G = nx.gnp_random_graph(50, 0.15, seed=s)
    for i, (u, v) in enumerate(G.edges()):
        G[u][v]["weight"] = i * 0.5
    H = fnx.Graph(); H.add_nodes_from(G.nodes()); H.add_edges_from((u, v, dict(d)) for u, v, d in G.edges(data=True))
    Gnx = _fnx_to_nx(H)
    if fc.to_dict_of_dicts(H) != nc.to_dict_of_dicts(Gnx):
        pf += 1
out["parity"]["default_weighted"] = {"checks": 80, "fails": pf}
G = nx.gnp_random_graph(40, 0.2, seed=1); H = fnx.Graph(); H.add_nodes_from(G.nodes()); H.add_edges_from(G.edges()); Gnx = _fnx_to_nx(H)
out["parity"]["nodelist"] = {"fails": int(fc.to_dict_of_dicts(H, nodelist=list(range(15))) != nc.to_dict_of_dicts(Gnx, nodelist=list(range(15))))}
out["parity"]["edge_data"] = {"fails": int(fc.to_dict_of_dicts(H, edge_data=1) != nc.to_dict_of_dicts(Gnx, edge_data=1))}
GD = nx.gnp_random_graph(40, 0.1, seed=3, directed=True); HD = fnx.DiGraph(); HD.add_nodes_from(GD.nodes()); HD.add_edges_from(GD.edges()); GDnx = _fnx_to_nx(HD)
out["parity"]["digraph"] = {"fails": int(fc.to_dict_of_dicts(HD) != nc.to_dict_of_dicts(GDnx))}

# speedup vs old submodule path (raw nx on fnx graph) and vs genuine nx
for n, p in [(1000, 0.01), (2000, 0.005)]:
    G = nx.gnp_random_graph(n, p, seed=7); H = fnx.Graph(); H.add_nodes_from(G.nodes()); H.add_edges_from(G.edges()); Gnx = _fnx_to_nx(H)
    routed = bench(lambda: fc.to_dict_of_dicts(H))
    old = bench(lambda: nc.to_dict_of_dicts(H))   # previous behavior: raw nx on fnx graph
    genuine = bench(lambda: nc.to_dict_of_dicts(Gnx))
    out["speedup"][f"n{n}"] = {"routed_ms": round(routed, 3), "old_submodule_ms": round(old, 3),
                              "genuine_nx_ms": round(genuine, 3),
                              "vs_old": round(old / routed, 1), "vs_nx": round(genuine / routed, 2)}

print(json.dumps(out, indent=2))
with open(sys.argv[1] if len(sys.argv) > 1 else "/tmp/c2d.json", "w") as f:
    json.dump(out, f, indent=2)
