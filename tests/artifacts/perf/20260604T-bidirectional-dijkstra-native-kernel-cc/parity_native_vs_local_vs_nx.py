import franken_networkx as fnx, networkx as nx, random, hashlib, json

# Build BOTH graphs (and the fnx local-path comparison) from one identical edge sequence.
def run_wrap(G, s, t, w):
    try:
        L,P = fnx.bidirectional_dijkstra(G,s,t,weight=w); return (type(L).__name__, repr(L), list(map(str,P)), None)
    except BaseException as e: return (None,None,None,f"{type(e).__name__}: {e}")
def run_local(G, s, t, w):
    try:
        L,P = fnx._bidirectional_dijkstra_local(G,s,t,w); return (type(L).__name__, repr(L), list(map(str,P)), None)
    except BaseException as e: return (None,None,None,f"{type(e).__name__}: {e}")
def run_nx(G, s, t, w):
    try:
        L,P = nx.bidirectional_dijkstra(G,s,t,weight=w); return (type(L).__name__, repr(L), list(map(str,P)), None)
    except BaseException as e: return (None,None,None,f"{type(e).__name__}: {e}")

def edgeseq(n,m,seed,wkind):
    rng=random.Random(seed); es=[]; seen=set()
    while len(es)<m:
        u=rng.randrange(n); v=rng.randrange(n)
        if u==v or (u,v) in seen or (v,u) in seen: continue
        seen.add((u,v))
        if wkind=="unit": es.append((u,v,{}))
        elif wkind=="int": es.append((u,v,{"weight":rng.randint(1,15)}))
        elif wkind=="float": es.append((u,v,{"weight":round(rng.uniform(0.1,9.9),4)}))
        else: es.append((u,v,{"weight":(rng.randint(1,9) if rng.random()<0.5 else round(rng.uniform(0.1,9.9),4))}))
    return es

mism_native_local=0; mism_native_nx=0; cases=0; golden=[]
for n,m in [(10,18),(30,80),(80,260),(150,500)]:
    for wkind in ["unit","int","float","mixed"]:
        for seed in range(6):
            es=edgeseq(n,m,seed,wkind)
            Gf=fnx.Graph(); Gf.add_nodes_from(range(n))
            Gn=nx.Graph(); Gn.add_nodes_from(range(n))
            for u,v,d in es:
                Gf.add_edge(u,v,**d); Gn.add_edge(u,v,**d)
            for (s,t) in [(0,n-1),(1,n//2),(2,n-2),(0,0),(3,7)]:
                cases+=1
                rnat=run_wrap(Gf,s,t,"weight")
                rloc=run_local(Gf,s,t,"weight")
                rnx =run_nx(Gn,s,t,"weight")
                if rnat!=rloc:
                    mism_native_local+=1
                    if mism_native_local<=6: print(f"NATIVE!=LOCAL n{n} {wkind} s{s} t{t}\n  loc:{rloc}\n  nat:{rnat}")
                if rnat!=rnx:
                    mism_native_nx+=1
                    if mism_native_nx<=6: print(f"NATIVE!=NX n{n} {wkind} s{s} t{t}\n  nx :{rnx}\n  nat:{rnat}")
                golden.append(json.dumps({"n":n,"w":wkind,"seed":seed,"st":[s,t],"r":rnat},sort_keys=True))
print(f"\nCASES={cases} native!=local={mism_native_local} native!=nx={mism_native_nx}")
print("GOLDEN_SHA256", hashlib.sha256("\n".join(golden).encode()).hexdigest())
