import franken_networkx as fnx, networkx as nx, random, json, hashlib
def build(M, seed, n=50, e=130, sl=True):
    g=M(); r=random.Random(seed)
    for x in [5,2,9,1]: g.add_node(x)
    g.add_nodes_from(range(n))
    for _ in range(e):
        u,v=r.randint(0,n-1),r.randint(0,n-1)
        if not sl and u==v: v=(v+1)%n
        k=r.randint(0,2)
        if k==0: g.add_edge(u,v,w=round(r.random(),3))
        elif k==1: g.add_edge(u,v,w=r.randint(1,9),tag="a")
        else: g.add_edge(u,v)
    return g
mism=0; records=[]
for seed in (1,2,3,4):
    for sl in (True,False):
        gf=build(fnx.DiGraph,seed,sl=sl); gn=build(nx.DiGraph,seed,sl=sl)
        # no-data, data=True, data=key
        for desc, fa, na in [
            ("nodata", lambda g: list(g.in_edges()), lambda g: list(g.in_edges())),
            ("data=True", lambda g: list(g.in_edges(data=True)), lambda g: list(g.in_edges(data=True))),
            ("data=w", lambda g: list(g.in_edges(data='w')), lambda g: list(g.in_edges(data='w'))),
            ("data=w,def0", lambda g: list(g.in_edges(data='w',default=0)), lambda g: list(g.in_edges(data='w',default=0))),
            ("data=miss", lambda g: list(g.in_edges(data='zz',default=7)), lambda g: list(g.in_edges(data='zz',default=7))),
        ]:
            f=fa(gf); n_=na(gn)
            if f!=n_:
                mism+=1
                for i,(a,b) in enumerate(zip(f,n_)):
                    if a!=b: print(f"  in_edges {desc} s={seed} sl={sl} i={i}: fnx={a} nx={b}"); break
            records.append([seed,sl,desc,f])
        # identity + dirty-sync for data=True
        ie=list(gf.in_edges(data=True))
        for s,t,d in ie[:5]:
            assert d is gf[s][t], f"identity fail {s},{t}"
        if ie:
            s,t,d=ie[0]; d["zz"]=1; assert gf[s][t].get("zz")==1; del gf[s][t]["zz"]
        # nbunch path unchanged
        nb=sorted(random.Random(seed).sample(range(50),10))
        if list(gf.in_edges(nb,data=True))!=list(gn.in_edges(nb,data=True)): mism+=1; print(f"  nbunch in_edges s={seed}")
blob=json.dumps(records, sort_keys=True, default=str).encode()
print(f"mismatches={mism}")
print(f"INEDGES_GOLDEN {hashlib.sha256(blob).hexdigest()}")
