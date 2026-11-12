import time, statistics, random, hashlib, json
import networkx as nx
import franken_networkx as fnx

def build(mod, n, m, seed, selfloops=False):
    rng=random.Random(seed)
    G=mod.Graph(); G.add_nodes_from(range(n))
    while G.number_of_edges() < m:
        u=rng.randrange(n); v=rng.randrange(n)
        if u!=v: G.add_edge(u,v)
    if selfloops:
        for _ in range(n//20):
            x=rng.randrange(n); G.add_edge(x,x)
    return G

# ---- parity across many random graphs (isomorphism: identical edge sequence) ----
mism=0; checked=0
for seed in range(60):
    n=rng_n=random.Random(seed).randrange(5,120)
    m=random.Random(seed+999).randrange(0, n*3)
    sl = (seed%3==0)
    # build identical graphs from identical edge sequence
    rng=random.Random(seed)
    edges=[]
    g0=nx.Graph(); g0.add_nodes_from(range(n))
    while g0.number_of_edges()<m:
        u=rng.randrange(n); v=rng.randrange(n)
        if u!=v:
            if not g0.has_edge(u,v): edges.append((u,v))
            g0.add_edge(u,v)
    if sl:
        for _ in range(n//20):
            x=random.Random(seed*7).randrange(n); edges.append((x,x)); g0.add_edge(x,x)
    gf=fnx.Graph(); gf.add_nodes_from(range(n)); gf.add_edges_from(edges)
    rn=nx.square_clustering(g0)
    rf=fnx.square_clustering(gf)
    checked+=1
    if rn.keys()!=rf.keys():
        mism+=1; print("KEY ORDER mismatch seed",seed); continue
    for k in rn:
        if abs(rn[k]-rf[k])>1e-15 or type(rn[k])!=type(rf[k]):
            # nx may give int 0 vs float; check value + type
            if rn[k]!=rf[k] or type(rn[k])!=type(rf[k]):
                mism+=1; print(f"seed {seed} node {k}: nx={rn[k]!r} fnx={rf[k]!r}"); break
print(f"PARITY: {checked} graphs checked, {mism} mismatches")

# ---- golden sha over a fixed corpus (values + key order + types) ----
def canon(d):
    return [[str(k), repr(v)] for k,v in d.items()]
golden={}
for seed in [1,2,3,7,11,42]:
    G=build(fnx, 200, 600, seed, selfloops=(seed%2==0))
    golden[f"s{seed}"]=canon(fnx.square_clustering(G))
sha=hashlib.sha256(json.dumps(golden,sort_keys=True).encode()).hexdigest()
print("GOLDEN_SHA(fnx)=",sha)
# nx reference sha on identical structure
goldn={}
for seed in [1,2,3,7,11,42]:
    Gf=build(fnx,200,600,seed,selfloops=(seed%2==0))
    Gn=nx.Graph(); Gn.add_nodes_from(Gf.nodes())
    Gn.add_edges_from(list(Gf.edges()))
    goldn[f"s{seed}"]=canon(nx.square_clustering(Gn))
shan=hashlib.sha256(json.dumps(goldn,sort_keys=True).encode()).hexdigest()
print("GOLDEN_SHA(nx )=",shan)
print("SHA MATCH:", sha==shan)
