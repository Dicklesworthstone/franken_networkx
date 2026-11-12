import sys, time, hashlib, json, random
sys.path.insert(0, "/data/projects/franken_networkx/python")
import networkx as nx, importlib
fnx = importlib.import_module("franken_networkx")


def cp(Gx):
    Gf = fnx.DiGraph()
    Gf.add_nodes_from(Gx.nodes())
    Gf.add_edges_from(Gx.edges())
    return Gf


# --- parity across many directed graphs ---
bad = 0
h_fnx = hashlib.sha256()
h_nx = hashlib.sha256()
TYPES = ["003","012","102","021D","021U","021C","111D","111U","030T","030C","201","120D","120U","120C","210","300"]
for seed in range(120):
    rnd = random.Random(seed)
    n = rnd.randint(0, 40)
    p = rnd.uniform(0.0, 0.25)
    Gx = nx.gnp_random_graph(n, p, seed=seed, directed=True)
    # also throw in some mutual edges
    if seed % 3 == 0:
        for u, v in list(Gx.edges()):
            if rnd.random() < 0.3:
                Gx.add_edge(v, u)
    Gf = cp(Gx)
    a = nx.triadic_census(Gx)
    b = fnx.triadic_census(Gf)
    if {k: a[k] for k in TYPES} != {k: b.get(k, 0) for k in TYPES}:
        bad += 1
        if bad <= 3:
            print("MISMATCH seed", seed, "n", n)
            print("  nx ", {k: a[k] for k in TYPES if a[k]})
            print("  fnx", {k: b.get(k,0) for k in TYPES if b.get(k,0)})
    h_fnx.update(json.dumps([b.get(k,0) for k in TYPES]).encode())
    h_nx.update(json.dumps([a[k] for k in TYPES]).encode())

print(f"\nparity: {120-bad}/120 graphs match")
print("golden_sha256_fnx =", h_fnx.hexdigest())
print("golden_sha256_nx  =", h_nx.hexdigest())
print("ISOMORPHISM:", "PASS" if h_fnx.hexdigest() == h_nx.hexdigest() else "FAIL")

# specific structural triads sanity (all 16 types reachable)
print("\n=== known small triads ===")
def t3(edges):
    G = fnx.DiGraph(); G.add_nodes_from([0,1,2]); G.add_edges_from(edges)
    c = fnx.triadic_census(G)
    Gn = nx.DiGraph(); Gn.add_nodes_from([0,1,2]); Gn.add_edges_from(edges)
    cn = nx.triadic_census(Gn)
    nonzero = {k:v for k,v in c.items() if v}
    ok = all(c.get(k,0)==cn[k] for k in TYPES)
    print(f"  {str(edges):40s} -> {nonzero}  {'ok' if ok else 'FAIL'}")
t3([])
t3([(0,1)])
t3([(0,1),(1,0)])
t3([(0,1),(0,2)])            # 021D
t3([(0,1),(0,2),(1,2)])      # 030T
t3([(0,1),(1,2),(2,0)])      # 030C
t3([(0,1),(1,0),(0,2),(2,0),(1,2),(2,1)])  # 300
