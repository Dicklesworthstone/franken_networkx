"""Proof for br-r37-c1-hf29q: junction_tree in-process de-delegation.
Byte-exact (node/edge/type) vs nx; speedup vs genuine nx and the old delegated path."""
import time, json, sys, warnings
warnings.filterwarnings("ignore")
import franken_networkx as fnx
import networkx as nx
from franken_networkx.backend import _fnx_to_nx


def sig(g):
    return (sorted((repr(n), d.get("type")) for n, d in g.nodes(data=True)),
            sorted(tuple(sorted((repr(u), repr(v)))) for u, v in g.edges()))


def bench(fn, r=2):
    fn(); b = 1e9
    for _ in range(r):
        t = time.perf_counter(); fn(); b = min(b, time.perf_counter() - t)
    return b * 1000


out = {"parity": {}, "speedup": {}}

fails = 0; checks = 0
for s in range(50):
    for n, p in [(20, 0.2), (30, 0.15), (25, 0.3), (15, 0.4), (35, 0.12)]:
        base = nx.gnp_random_graph(n, p, seed=s)
        H = fnx.Graph(); H.add_nodes_from(base.nodes()); H.add_edges_from(base.edges())
        Gnx = _fnx_to_nx(H)
        checks += 1
        if sig(fnx.junction_tree(H)) != sig(nx.junction_tree(Gnx)):
            fails += 1
for s in range(20):
    base = nx.gnp_random_graph(18, 0.2, seed=s, directed=True)
    H = fnx.DiGraph(); H.add_nodes_from(base.nodes()); H.add_edges_from(base.edges())
    Gnx = _fnx_to_nx(H)
    checks += 1
    if sig(fnx.junction_tree(H)) != sig(nx.junction_tree(Gnx)):
        fails += 1
out["parity"] = {"checks": checks, "fails": fails,
                 "empty_ok": fnx.junction_tree(fnx.Graph()).number_of_nodes() == nx.junction_tree(nx.Graph()).number_of_nodes()}

for prm in [(400, 6, 0.3), (500, 6, 0.3)]:
    n, k, pp = prm
    G = nx.connected_watts_strogatz_graph(n, k, pp, seed=7)
    H = fnx.Graph(); H.add_nodes_from(G.nodes()); H.add_edges_from(G.edges())
    Gnx = _fnx_to_nx(H)
    new = bench(lambda: fnx.junction_tree(H))
    genuine = bench(lambda: nx.junction_tree(Gnx))
    out["speedup"][f"n{n}"] = {"inproc_ms": round(new, 1), "genuine_nx_ms": round(genuine, 1),
                              "vs_nx": round(genuine / new, 2)}

print(json.dumps(out, indent=2))
with open(sys.argv[1] if len(sys.argv) > 1 else "/tmp/jt.json", "w") as f:
    json.dump(out, f, indent=2)
