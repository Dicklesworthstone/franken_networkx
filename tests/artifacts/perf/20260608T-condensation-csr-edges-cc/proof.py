import time,statistics,random,hashlib,json
import networkx as nx, franken_networkx as fnx
def build(mod,n,m,seed,sl=False,multi=False):
    rng=random.Random(seed)
    cls = mod.MultiDiGraph if multi else mod.DiGraph
    G=cls(); G.add_nodes_from(range(n)); 
    for _ in range(m):
        u=rng.randrange(n); v=rng.randrange(n)
        if u!=v or sl: G.add_edge(u,v)
    return G
def canon(C):
    return {
      "nodes": list(C.nodes()),
      "edges": list(C.edges()),
      "members": [[str(n), sorted(map(str, C.nodes[n]["members"]))] for n in C.nodes()],
      "mapping": sorted((str(k),v) for k,v in C.graph["mapping"].items()),
    }
mism=0;checked=0
for seed in range(60):
    multi=(seed%5==0); sl=(seed%4==0)
    n=random.Random(seed).randrange(2,60); m=random.Random(seed+1).randrange(0,n*3)
    gn=build(nx,n,m,seed,sl,multi)
    gf=build(fnx,n,m,seed,sl,multi) if not multi else None
    if multi:
        # build fnx multidigraph from same edges
        gf=fnx.MultiDiGraph(); gf.add_nodes_from(range(n)); gf.add_edges_from(list(gn.edges()))
    else:
        gf=fnx.DiGraph(); gf.add_nodes_from(range(n)); gf.add_edges_from(list(gn.edges()))
    cn=nx.condensation(gn); cf=fnx.condensation(gf)
    checked+=1
    if canon(cn)!=canon(cf):
        mism+=1
        if mism<=3:
            a,b=canon(cn),canon(cf)
            for k in a:
                if a[k]!=b[k]: print(f"seed{seed} multi{multi} key {k}: nx={a[k]} fnx={b[k]}"); break
print(f"PARITY: {checked} graphs, {mism} mismatches")
# golden
gf_d={};gn_d={}
for seed in [1,2,7,42,99]:
    gn=build(nx,80,400,seed)
    gf=fnx.DiGraph(); gf.add_nodes_from(range(80)); gf.add_edges_from(list(gn.edges()))
    gn_d[seed]=canon(nx.condensation(gn)); gf_d[seed]=canon(fnx.condensation(gf))
shn=hashlib.sha256(json.dumps(gn_d,sort_keys=True).encode()).hexdigest()
shf=hashlib.sha256(json.dumps(gf_d,sort_keys=True).encode()).hexdigest()
print("GOLDEN MATCH:",shn==shf,shf[:16])
def bench(fn,reps=5):
    ts=[]
    for _ in range(reps):
        t=time.perf_counter(); fn(); ts.append(time.perf_counter()-t)
    return statistics.median(ts)
for (n,m) in [(2000,12000),(4000,24000)]:
    gn=build(nx,n,m,7)
    gf=fnx.DiGraph(); gf.add_nodes_from(range(n)); gf.add_edges_from(list(gn.edges()))
    tn=bench(lambda:nx.condensation(gn)); tf=bench(lambda:fnx.condensation(gf))
    print(f"n={n} m={m}: nx={tn*1e3:8.2f}ms fnx={tf*1e3:7.2f}ms speedup={tn/tf:6.2f}x")
