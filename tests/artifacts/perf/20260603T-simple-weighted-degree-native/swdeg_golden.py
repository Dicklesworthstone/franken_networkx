import franken_networkx as fnx, networkx as nx, random, json, hashlib

def build(M, seed, n=40, e=120, selfloops=True):
    r = random.Random(seed); g = M(); g.add_nodes_from(range(n))
    for i in range(e):
        u, v = r.randint(0, n-1), r.randint(0, n-1)
        if not selfloops and u == v: v = (v+1) % n
        kind = r.randint(0, 3)
        if kind == 0: g.add_edge(u, v, w=r.randint(1, 9))
        elif kind == 1: g.add_edge(u, v, w=r.random()*5.0)
        elif kind == 2: g.add_edge(u, v)
        else: g.add_edge(u, v, w=r.randint(1, 9), other=2)
    return g

records=[]; mism=0
for label, Mf, Mn in [("Graph", fnx.Graph, nx.Graph), ("DiGraph", fnx.DiGraph, nx.DiGraph)]:
    for seed in (1,2,3):
        for sl in (True, False):
            gf=build(Mf, seed, selfloops=sl); gn=build(Mn, seed, selfloops=sl)
            df=list(gf.degree(weight='w')); dn=list(gn.degree(weight='w'))
            if df != dn:
                mism+=1
                for i,(a,b) in enumerate(zip(df,dn)):
                    if a!=b: print(f"  MISMATCH {label} s={seed} sl={sl} i={i}: fnx={a!r} nx={b!r}"); break
            for (nf,vf),(nn,vn) in zip(df,dn):
                if type(vf) is not type(vn): mism+=1; print(f"  TYPE {label} {nf}: {type(vf).__name__} vs {type(vn).__name__}")
            # single-node + nbunch fallback
            for node in list(gf.nodes())[:5]:
                if gf.degree(node, weight='w') != gn.degree(node, weight='w'):
                    mism+=1; print(f"  SINGLE {label} node={node}: {gf.degree(node,weight='w')!r} vs {gn.degree(node,weight='w')!r}")
            sub=list(gf.nodes())[:8]
            if dict(gf.degree(sub, weight='w')) != dict(gn.degree(sub, weight='w')):
                mism+=1; print(f"  NBUNCH {label}")
            # DiGraph in/out weighted unchanged-correctness
            if label=="DiGraph":
                if list(gf.in_degree(weight='w'))!=list(gn.in_degree(weight='w')): mism+=1; print(f"  IN {label}")
                if list(gf.out_degree(weight='w'))!=list(gn.out_degree(weight='w')): mism+=1; print(f"  OUT {label}")
            records.append([label,seed,sl,[[n,(round(v,12) if isinstance(v,float) else v)] for n,v in df]])
blob=json.dumps(records, sort_keys=True).encode()
print(f"mismatches={mism}")
print(f"SWDEG_GOLDEN {hashlib.sha256(blob).hexdigest()}")
