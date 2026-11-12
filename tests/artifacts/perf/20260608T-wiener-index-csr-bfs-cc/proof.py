import time,statistics,random,hashlib,json,math
import networkx as nx, franken_networkx as fnx
def build_pair(n,m,seed,directed=False,sl=False):
    rng=random.Random(seed)
    gn=(nx.DiGraph() if directed else nx.Graph()); gn.add_nodes_from(range(n)); edges=[]
    while gn.number_of_edges()<m:
        u=rng.randrange(n); v=rng.randrange(n)
        if u!=v and not gn.has_edge(u,v): edges.append((u,v)); gn.add_edge(u,v)
    if sl:
        for _ in range(max(1,n//20)):
            x=rng.randrange(n)
            if not gn.has_edge(x,x): edges.append((x,x)); gn.add_edge(x,x)
    gf=(fnx.DiGraph() if directed else fnx.Graph()); gf.add_nodes_from(range(n)); gf.add_edges_from(edges)
    return gn,gf
mism=0;checked=0
for seed in range(60):
    directed=(seed%3==0); sl=(seed%4==0)
    n=random.Random(seed).randrange(3,70); m=random.Random(seed+1).randrange(0,n*4)
    gn,gf=build_pair(n,m,seed,directed,sl)
    rn=nx.wiener_index(gn); rf=fnx.wiener_index(gf)
    checked+=1
    same = (rn==rf) or (math.isinf(rn) and math.isinf(rf)) or (isinstance(rn,float) and isinstance(rf,float) and abs(rn-rf)<1e-9)
    # also match type for directed int vs undirected float
    if same and not math.isinf(rn): same = (type(rn)==type(rf))
    if not same:
        mism+=1; print(f"seed{seed} dir{directed} sl{sl}: nx={rn!r} fnx={rf!r}")
print(f"PARITY: {checked} graphs, {mism} mismatches")
# golden sha
gf_d={};gn_d={}
for seed in [1,2,7,42,99,123]:
    for directed in (False,True):
        gn,gf=build_pair(60,300 if not directed else 600,seed,directed)  # dense->connected
        gf_d[f"s{seed}d{directed}"]=repr(fnx.wiener_index(gf))
        gn_d[f"s{seed}d{directed}"]=repr(nx.wiener_index(gn))
shf=hashlib.sha256(json.dumps(gf_d,sort_keys=True).encode()).hexdigest()
shn=hashlib.sha256(json.dumps(gn_d,sort_keys=True).encode()).hexdigest()
print("GOLDEN MATCH:", shf==shn, shf[:16])
# bench
def bench(fn,reps=5):
    ts=[]
    for _ in range(reps):
        t=time.perf_counter(); fn(); ts.append(time.perf_counter()-t)
    return statistics.median(ts)
for (n,m,d) in [(400,3000,False),(800,6000,False),(400,3000,True)]:
    gn,gf=build_pair(n,m,7,d)
    tn=bench(lambda:nx.wiener_index(gn)); tf=bench(lambda:fnx.wiener_index(gf))
    print(f"n={n} m={m} dir={d}: nx={tn*1e3:8.2f}ms fnx={tf*1e3:7.2f}ms speedup={tn/tf:6.2f}x")
