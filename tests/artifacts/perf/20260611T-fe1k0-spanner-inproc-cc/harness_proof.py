"""Proof for br-r37-c1-fe1k0: in-process Baswana-Sen spanner.
Spanner is randomized + node-identity-tie-broken -> parity is STRUCTURAL
(valid spanner with the requested stretch), not exact-edge. Validate validity +
input contracts + speedup vs genuine nx and vs the native _raw_spanner kernel."""
import time, json, sys, warnings, random
warnings.filterwarnings("ignore")
import franken_networkx as fnx
import networkx as nx
import networkx.algorithms.sparsifiers as nsp
from franken_networkx.backend import _fnx_to_nx


def bench(fn, r=6):
    fn(); b = 1e9
    for _ in range(r):
        t = time.perf_counter(); fn(); b = min(b, time.perf_counter() - t)
    return b * 1000


def valid(orig, cand, st, weight=None):
    if set(orig.nodes()) != set(cand.nodes()):
        return False
    for u, v in cand.edges():
        if not orig.has_edge(u, v):
            return False
        if weight is not None and cand[u][v][weight] != orig[u][v][weight]:
            return False
    for u in orig.nodes():
        d = (nx.single_source_dijkstra_path_length(orig, u, weight=weight) if weight
             else nx.single_source_shortest_path_length(orig, u))
        dc = (nx.single_source_dijkstra_path_length(cand, u, weight=weight) if weight
              else nx.single_source_shortest_path_length(cand, u))
        for v, ol in d.items():
            if dc.get(v, 1e18) > st * ol + 1e-9:
                return False
    return True


def err(fn):
    try:
        fn(); return None
    except Exception as e:
        return type(e).__name__


out = {"contracts": {}, "validity": {}, "speedup": {}}
out["contracts"] = {
    "directed": err(lambda: fnx.spanner(fnx.DiGraph([(0, 1)]), 2)),
    "multigraph": err(lambda: fnx.spanner(fnx.MultiGraph([(0, 1), (0, 1)]), 2)),
    "stretch0": err(lambda: fnx.spanner(fnx.path_graph(5), 0)),
    "empty": err(lambda: fnx.spanner(fnx.Graph(), 2)),
    "submodule_routed": fnx.sparsifiers.spanner is not nsp.spanner,
}

# validity over many graphs/stretches incl weighted
inval = 0; checks = 0
for s in range(30):
    for n, p in [(60, 0.1), (90, 0.07), (50, 0.2)]:
        for st in [3, 5, 7]:
            base = nx.gnp_random_graph(n, p, seed=s)
            H = fnx.Graph(); H.add_nodes_from(base.nodes()); H.add_edges_from(base.edges())
            Hnx = nx.Graph(); Hnx.add_nodes_from(H); Hnx.add_edges_from(H.edges())
            R = fnx.spanner(H, st, seed=s)
            cand = nx.Graph(); cand.add_nodes_from(R); cand.add_edges_from(R.edges())
            checks += 1
            if not valid(Hnx, cand, st):
                inval += 1
# weighted
for s in range(15):
    rng = random.Random(s); base = nx.gnp_random_graph(60, 0.12, seed=s)
    H = fnx.Graph(); H.add_nodes_from(base.nodes())
    H.add_edges_from((u, v, {"weight": rng.randint(1, 9)}) for u, v in base.edges())
    Hnx = nx.Graph(); Hnx.add_nodes_from(H)
    Hnx.add_edges_from((u, v, {"weight": H[u][v]["weight"]}) for u, v in H.edges())
    R = fnx.spanner(H, 4, weight="weight", seed=s)
    cand = nx.Graph(); cand.add_nodes_from(R)
    cand.add_edges_from((u, v, {"weight": R[u][v]["weight"]}) for u, v in R.edges())
    checks += 1
    if not valid(Hnx, cand, 4, weight="weight"):
        inval += 1
out["validity"] = {"checks": checks, "invalid": inval}

for n, p in [(400, 0.04), (800, 0.02), (1500, 0.01)]:
    G = nx.gnp_random_graph(n, p, seed=7); H = fnx.Graph(); H.add_nodes_from(G.nodes()); H.add_edges_from(G.edges()); Gnx = _fnx_to_nx(H)
    new = bench(lambda: fnx.spanner(H, 3, seed=42))
    genuine = bench(lambda: nsp.spanner(Gnx, 3, seed=42))
    out["speedup"][f"n{n}"] = {"inproc_ms": round(new, 2), "genuine_nx_ms": round(genuine, 2),
                              "vs_nx": round(genuine / new, 2)}

print(json.dumps(out, indent=2))
with open(sys.argv[1] if len(sys.argv) > 1 else "/tmp/sp.json", "w") as f:
    json.dump(out, f, indent=2)
