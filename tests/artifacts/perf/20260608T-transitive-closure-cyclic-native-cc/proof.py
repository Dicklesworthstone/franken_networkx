import time,statistics,random,hashlib,json
import networkx as nx, franken_networkx as fnx
def build_edges(n,m,seed,sl=False):
    rng=random.Random(seed); edges=[]; seen=set()
    while len(seen)<m:
        u=rng.randrange(n); v=rng.randrange(n)
        if (u!=v or sl) and (u,v) not in seen: seen.add((u,v)); edges.append((u,v))
    return edges
def canon(C):
    # set of edges + node attrs + edge attrs + class
    return {
      "type": type(C).__name__,
      "nodes": sorted(map(str,C.nodes())),
      "edges": sorted((str(u),str(v)) for u,v in C.edges()),
      "nodeattr": sorted((str(n),sorted(d.items())) for n,d in C.nodes(data=True) if d),
      "edgeattr": sorted((str(u),str(v),sorted(d.items())) for u,v,d in C.edges(data=True) if d),
    }
mism=0;checked=0
for seed in range(80):
    n=random.Random(seed).randrange(2,50); m=random.Random(seed+1).randrange(0,n*3)
    sl=(seed%5==0)
    edges=build_edges(n,m,seed,sl)
    gn=nx.DiGraph(); gn.add_nodes_from(range(n)); gn.add_edges_from(edges)
    gf=fnx.DiGraph(); gf.add_nodes_from(range(n)); gf.add_edges_from(edges)
    # attrs on some
    if seed%3==0:
        for (u,v) in edges[:3]: gn[u][v]["w"]=u+v; gf[u][v]["w"]=u+v
        gn.nodes[0]["c"]="x"; gf.nodes[0]["c"]="x"
    rn=nx.transitive_closure(gn); rf=fnx.transitive_closure(gf)
    checked+=1
    if canon(rn)!=canon(rf):
        mism+=1
        if mism<=4:
            a,b=canon(rn),canon(rf)
            for k in a:
                if a[k]!=b[k]: print(f"seed{seed} n{n} key {k} DIFF len nx={len(a[k]) if isinstance(a[k],list) else a[k]} fnx={len(b[k]) if isinstance(b[k],list) else b[k]}"); break
print(f"PARITY: {checked} graphs, {mism} mismatches")
# golden over fixed corpus
gn_d={};gf_d={}
for seed in [1,3,7,11,42]:
    edges=build_edges(40,160,seed,sl=(seed%2==0))
    gn=nx.DiGraph(); gn.add_nodes_from(range(40)); gn.add_edges_from(edges)
    gf=fnx.DiGraph(); gf.add_nodes_from(range(40)); gf.add_edges_from(edges)
    gn_d[seed]=canon(nx.transitive_closure(gn)); gf_d[seed]=canon(fnx.transitive_closure(gf))
shn=hashlib.sha256(json.dumps(gn_d,sort_keys=True).encode()).hexdigest()
shf=hashlib.sha256(json.dumps(gf_d,sort_keys=True).encode()).hexdigest()
print("GOLDEN MATCH:",shn==shf,shf[:16])
def bench(fn,reps=3):
    ts=[]
    for _ in range(reps):
        t=time.perf_counter(); fn(); ts.append(time.perf_counter()-t)
    return statistics.median(ts)
for (n,m) in [(500,2500),(800,4000)]:
    edges=build_edges(n,m,7)
    gn=nx.DiGraph(); gn.add_nodes_from(range(n)); gn.add_edges_from(edges)
    gf=fnx.DiGraph(); gf.add_nodes_from(range(n)); gf.add_edges_from(edges)
    tn=bench(lambda:nx.transitive_closure(gn)); tf=bench(lambda:fnx.transitive_closure(gf))
    print(f"cyclic n={n} m={m}: nx={tn*1e3:8.1f}ms fnx={tf*1e3:7.1f}ms speedup={tn/tf:6.2f}x")
