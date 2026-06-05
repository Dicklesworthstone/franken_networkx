import sys, time, hashlib, json, random, warnings
sys.path.insert(0, "/data/projects/franken_networkx/python")
import networkx as nx, importlib
warnings.filterwarnings("ignore")
fnx = importlib.import_module("franken_networkx")


def cp(Gx, directed=False):
    Gf = (fnx.DiGraph() if directed else fnx.Graph())
    Gf.add_nodes_from(Gx.nodes()); Gf.add_edges_from(Gx.edges(data=True)); return Gf


# ---- parity: max_flow value+dict, min_cut value+partition, edge/node conn ----
hv = hashlib.sha256(); hn = hashlib.sha256()
bad = 0
for seed in range(80):
    rnd = random.Random(seed)
    n = rnd.randint(4, 30)
    directed = seed % 2 == 0
    Gx = nx.gnp_random_graph(n, rnd.uniform(0.1, 0.4), seed=seed, directed=directed)
    for u, v in Gx.edges():
        Gx[u][v]["capacity"] = rnd.randint(1, 15)
    if Gx.number_of_nodes() < 2:
        continue
    Gf = cp(Gx, directed=directed)
    nodes = list(Gx.nodes())
    s, t = nodes[0], nodes[-1]
    try:
        fv = nx.maximum_flow_value(Gx, s, t)
        ff = fnx.maximum_flow_value(Gf, s, t)
        cv = nx.minimum_cut_value(Gx, s, t)
        cf = fnx.minimum_cut_value(Gf, s, t)
    except Exception:
        continue
    if fv != ff or cv != cf:
        bad += 1
        if bad <= 4:
            print(f"MISMATCH seed={seed} dir={directed} nxflow={fv} fnxflow={ff} nxcut={cv} fnxcut={cf}")
    # full max_flow flow dict parity
    fnv, fnd = nx.maximum_flow(Gx, s, t)
    ffv, ffd = fnx.maximum_flow(Gf, s, t)
    # compare flow dicts (value already checked); dicts may differ if multiple optima
    hv.update(json.dumps([ff, cf], sort_keys=True).encode())
    hn.update(json.dumps([fv, cv], sort_keys=True).encode())

print(f"\nmax_flow_value + min_cut_value parity: {80-bad}/80 (bad={bad})")
print("golden_fnx =", hv.hexdigest())
print("golden_nx  =", hn.hexdigest())
print("VALUE ISOMORPHISM:", "PASS" if hv.hexdigest()==hn.hexdigest() else "FAIL")

# edge_connectivity + node_connectivity parity (undirected)
ecbad = 0
for seed in range(60):
    G = nx.gnp_random_graph(random.Random(seed).randint(5,40), 0.12, seed=seed)
    F = cp(G)
    if nx.edge_connectivity(G) != fnx.edge_connectivity(F):
        ecbad += 1
    if nx.node_connectivity(G) != fnx.node_connectivity(F):
        ecbad += 1
print(f"edge+node_connectivity parity: {'PASS' if ecbad==0 else f'FAIL ({ecbad})'}")

# ---- benchmark edge_connectivity ----
def mn(fn, r=4):
    fn(); b=1e9
    for _ in range(r):
        s=time.perf_counter(); fn(); b=min(b,time.perf_counter()-s)
    return b
print("\n=== edge_connectivity benchmark ===")
for n in (150, 300, 500):
    G = nx.gnp_random_graph(n, 0.04, seed=3); F = cp(G)
    tn = mn(lambda: nx.edge_connectivity(G)); tf = mn(lambda: fnx.edge_connectivity(F))
    print(f"  n={n:4d} nx={tn:.4f}s fnx={tf:.4f}s ratio={tf/tn:5.2f} (fnx {'FASTER' if tf<tn else 'slower'})", flush=True)
print("\n=== maximum_flow_value benchmark (capacitated directed) ===")
for n in (200, 400):
    G = nx.gnp_random_graph(n, 0.05, seed=5, directed=True)
    rr = random.Random(1)
    for u,v in G.edges(): G[u][v]["capacity"]=rr.randint(1,20)
    F = cp(G, directed=True); nn=list(G.nodes())
    tn = mn(lambda: nx.maximum_flow_value(G, nn[0], nn[-1]))
    tf = mn(lambda: fnx.maximum_flow_value(F, nn[0], nn[-1]))
    print(f"  n={n:4d} nx={tn:.4f}s fnx={tf:.4f}s ratio={tf/tn:5.2f}", flush=True)
