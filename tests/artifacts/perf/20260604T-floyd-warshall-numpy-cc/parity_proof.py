import franken_networkx as fnx
import networkx as nx
import random, math, json, hashlib

def norm(d):
    # canonicalize nested dict-of-dicts: keys as str, values with inf marker, preserve ORDER
    out = []
    for u, row in d.items():
        inner = []
        for v, val in row.items():
            if isinstance(val, float) and math.isinf(val):
                token = "inf"
            else:
                token = (type(val).__name__, val)
            inner.append((str(u), str(v), str(token)))
        out.append(inner)
    return out

rng = random.Random(12345)
cases = 0
mismatch = 0
golden_lines = []

def check(G_fnx, G_nx, weight, label):
    global cases, mismatch
    cases += 1
    try:
        rf = fnx.floyd_warshall(G_fnx, weight=weight)
    except Exception as e:
        rf = ("ERR", type(e).__name__)
    try:
        rn = nx.floyd_warshall(G_nx, weight=weight)
    except Exception as e:
        rn = ("ERR", type(e).__name__)
    nf = norm(rf) if isinstance(rf, dict) else rf
    nn = norm(rn) if isinstance(rn, dict) else rn
    ok = (nf == nn)
    if not ok:
        mismatch += 1
        print("MISMATCH", label)
        if isinstance(rf, dict) and isinstance(rn, dict):
            # find first diff
            for a,b in zip(nf, nn):
                if a != b:
                    print("  fnx:", a[:3])
                    print("  nx :", b[:3])
                    break
    golden_lines.append(json.dumps({"label": label, "fnx": nf if isinstance(nf,list) else list(nf), "match": ok}, sort_keys=True, default=str))

for n in [0,1,2,5,8,15,25]:
    for directed in [False, True]:
        for wkind in ["unit","int","float","mixed"]:
            G = (nx.DiGraph() if directed else nx.Graph())
            G.add_nodes_from(range(n))
            edges = []
            for _ in range(n*2):
                u = rng.randrange(max(n,1)); v = rng.randrange(max(n,1))
                if u==v: continue
                edges.append((u,v))
            for (u,v) in edges:
                if wkind=="unit":
                    G.add_edge(u,v)
                elif wkind=="int":
                    G.add_edge(u,v,weight=rng.randint(1,10))
                elif wkind=="float":
                    G.add_edge(u,v,weight=round(rng.uniform(0.1,5.0),3))
                else:
                    G.add_edge(u,v,weight=(rng.randint(1,5) if rng.random()<0.5 else round(rng.uniform(0.1,5.0),3)))
            Gf = fnx.from_networkx(G) if hasattr(fnx,'from_networkx') else None
            # build fnx graph mirroring same construction
            Gf = (fnx.DiGraph() if directed else fnx.Graph())
            Gf.add_nodes_from(range(n))
            for (u,v) in edges:
                if wkind=="unit":
                    Gf.add_edge(u,v)
                elif wkind=="int":
                    pass
            # easier: rebuild from G's edges to keep identical weights
            Gf = (fnx.DiGraph() if directed else fnx.Graph())
            Gf.add_nodes_from(range(n))
            for u,v,data in G.edges(data=True):
                Gf.add_edge(u,v,**data)
            check(Gf, G, "weight", f"n{n}_d{directed}_{wkind}")

# negative weights (no neg cycle): a path graph with negatives
G = nx.DiGraph(); G.add_nodes_from(range(5))
G.add_edge(0,1,weight=-2); G.add_edge(1,2,weight=-1); G.add_edge(2,3,weight=3); G.add_edge(3,4,weight=-1)
Gf = fnx.DiGraph(); Gf.add_nodes_from(range(5))
for u,v,d in G.edges(data=True): Gf.add_edge(u,v,**d)
check(Gf,G,"weight","neg_dag")

# string nodes
G = nx.Graph(); G.add_edges_from([("a","b",{"weight":2}),("b","c",{"weight":3}),("a","c",{"weight":10})])
Gf = fnx.Graph()
for u,v,d in G.edges(data=True): Gf.add_edge(u,v,**d)
check(Gf,G,"weight","str_nodes")

# multigraph
G = nx.MultiGraph(); G.add_edge(0,1,weight=5); G.add_edge(0,1,weight=2); G.add_edge(1,2,weight=1)
Gf = fnx.MultiGraph()
for u,v,d in G.edges(data=True): Gf.add_edge(u,v,**d)
check(Gf,G,"weight","multigraph")

# weight=None (unit)
G = nx.Graph(); G.add_edges_from([(0,1),(1,2),(2,3)])
Gf = fnx.Graph(); 
for u,v in G.edges(): Gf.add_edge(u,v)
check(Gf,G,None,"weight_none")

print(f"\nCASES={cases} MISMATCH={mismatch}")
blob = "\n".join(golden_lines)
print("GOLDEN_SHA256", hashlib.sha256(blob.encode()).hexdigest())
