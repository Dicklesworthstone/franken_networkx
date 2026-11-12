import random, math
import franken_networkx as fnx
import networkx as nx

def build(GnX):
    H = fnx.Graph()
    H.add_nodes_from(GnX.nodes(data=True))
    H.add_edges_from((u, v, dict(d)) for u, v, d in GnX.edges(data=True))
    return H

def edge_list(it, data):
    out = []
    for e in it:
        if data:
            u, v, d = e
            out.append((u, v, d.get("weight")))
        else:
            out.append(tuple(e))
    return out

fails = 0
checks = 0

# 1) random graphs, varied sizes/seeds, min & max, data True/False
for seed in range(60):
    for n, m in [(0,0),(1,0),(2,1),(20,40),(50,150),(100,400),(7,9),(300,1200)]:
        rng = random.Random(seed*13+n)
        G = nx.gnm_random_graph(n, m, seed=seed)
        for u,v in G.edges():
            G[u][v]["weight"] = rng.random()
        H = build(G)
        for algo_fn_nx, algo_fn_fnx, minimum in [
            (nx.minimum_spanning_edges, fnx.minimum_spanning_edges, True),
            (nx.maximum_spanning_edges, fnx.maximum_spanning_edges, False),
        ]:
            for data in (True, False):
                ref = edge_list(algo_fn_nx(G, algorithm="boruvka", weight="weight", data=data), data)
                got = edge_list(algo_fn_fnx(H, algorithm="boruvka", weight="weight", data=data), data)
                checks += 1
                if ref != got:
                    fails += 1
                    if fails <= 8:
                        print(f"MISMATCH random n={n} m={m} seed={seed} min={minimum} data={data}")
                        print("  ref", ref[:6]); print("  got", got[:6])

# 2) disconnected graphs (forest result)
for seed in range(30):
    rng = random.Random(seed)
    G = nx.Graph()
    G.add_nodes_from(range(40))
    # two clusters, no bridge
    for _ in range(60):
        a = rng.randint(0,19); b = rng.randint(0,19)
        if a!=b: G.add_edge(a,b,weight=rng.random())
    for _ in range(60):
        a = rng.randint(20,39); b = rng.randint(20,39)
        if a!=b: G.add_edge(a,b,weight=rng.random())
    H = build(G)
    ref = edge_list(nx.minimum_spanning_edges(G, algorithm="boruvka", data=True), True)
    got = edge_list(fnx.minimum_spanning_edges(H, algorithm="boruvka", data=True), True)
    checks += 1
    if ref != got:
        fails += 1; print(f"MISMATCH disconnected seed={seed}"); print(" ref",ref[:6]); print(" got",got[:6])

# 3) string & tuple node keys
for seed in range(25):
    rng = random.Random(seed)
    base = nx.gnm_random_graph(35, 90, seed=seed)
    G = nx.Graph()
    mp = {i: (f"v{i}" if seed%2 else (i, i*i)) for i in base}
    G.add_nodes_from(mp[i] for i in base)
    for u,v in base.edges():
        G.add_edge(mp[u], mp[v], weight=rng.random())
    H = build(G)
    ref = edge_list(nx.minimum_spanning_edges(G, algorithm="boruvka", data=True), True)
    got = edge_list(fnx.minimum_spanning_edges(H, algorithm="boruvka", data=True), True)
    checks += 1
    if ref != got:
        fails += 1; print(f"MISMATCH keyed seed={seed}"); print(" ref",ref[:6]); print(" got",got[:6])

# 4) all default weight (missing weight attr) -> defaults to 1
for seed in range(15):
    G = nx.gnm_random_graph(40, 120, seed=seed)  # no weight attrs
    H = build(G)
    ref = edge_list(nx.minimum_spanning_edges(G, algorithm="boruvka", weight="weight", data=True), True)
    got = edge_list(fnx.minimum_spanning_edges(H, algorithm="boruvka", weight="weight", data=True), True)
    checks += 1
    if ref != got:
        fails += 1; print(f"MISMATCH unitw seed={seed}"); print(" ref",ref[:6]); print(" got",got[:6])

# 5) NaN weight: both must raise ValueError (bail path)
G = nx.path_graph(5)
for u,v in G.edges(): G[u][v]["weight"]=1.0
G[1][2]["weight"]=float("nan")
H = build(G)
import traceback
def raises(fn):
    try:
        list(fn()); return None
    except Exception as e:
        return type(e).__name__
rnx = raises(lambda: nx.minimum_spanning_edges(G, algorithm="boruvka", data=True))
rfx = raises(lambda: fnx.minimum_spanning_edges(H, algorithm="boruvka", data=True))
checks += 1
if rnx != rfx:
    fails += 1; print(f"MISMATCH nan: nx={rnx} fnx={rfx}")
# ignore_nan=True path
rnx2 = edge_list(nx.minimum_spanning_edges(G, algorithm="boruvka", data=True, ignore_nan=True), True)
rfx2 = edge_list(fnx.minimum_spanning_edges(H, algorithm="boruvka", data=True, ignore_nan=True), True)
checks += 1
if rnx2 != rfx2:
    fails += 1; print(f"MISMATCH nan-ignore: nx={rnx2} fnx={rfx2}")

# 6) minimum_spanning_tree graph form
for seed in range(15):
    rng = random.Random(seed)
    G = nx.gnm_random_graph(50, 200, seed=seed)
    for u,v in G.edges(): G[u][v]["weight"]=rng.random()
    H = build(G)
    Tn = nx.minimum_spanning_tree(G, algorithm="boruvka", weight="weight")
    Tf = fnx.minimum_spanning_tree(H, algorithm="boruvka", weight="weight")
    checks += 1
    en = sorted((min(u,v),max(u,v)) for u,v in Tn.edges())
    ef = sorted((min(u,v),max(u,v)) for u,v in Tf.edges())
    if en != ef:
        fails += 1; print(f"MISMATCH mst-graph seed={seed}")

print(f"DONE checks={checks} fails={fails}")
