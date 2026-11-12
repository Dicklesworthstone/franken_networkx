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
        f=list(gf.edges(data=True)); n_=list(gn.edges(data=True))
        if f!=n_:
            mism+=1
            for i,(a,b) in enumerate(zip(f,n_)):
                if a!=b: print(f"  EDGES(data) s={seed} sl={sl} i={i}: fnx={a} nx={b}"); break
        # identity: yielded data dict is G[u][v]
        for u,v,d in f[:5]:
            assert d is gf[u][v], f"identity fail {u},{v}"
        # mutation visible
        if f:
            u,v,d=f[0]; d["zz"]=1
            assert gf[u][v].get("zz")==1; del gf[u][v]["zz"]
        # out_edges(data=True) parity
        if list(gf.out_edges(data=True))!=list(gn.out_edges(data=True)): mism+=1; print(f"  OUT_EDGES s={seed} sl={sl}")
        # data=False and data='w' unchanged-correct
        if list(gf.edges())!=list(gn.edges()): mism+=1; print(f"  EDGES nodata s={seed}")
        if list(gf.edges(data='w'))!=list(gn.edges(data='w')): mism+=1; print(f"  EDGES data=w s={seed}")
        # nbunch path unchanged
        nb=sorted(random.Random(seed).sample(range(50),10))
        if list(gf.edges(nb,data=True))!=list(gn.edges(nb,data=True)): mism+=1; print(f"  EDGES nbunch s={seed}")
        records.append([seed,sl,[(u,v,sorted(d.items())) for u,v,d in f]])
blob=json.dumps(records, sort_keys=True).encode()
print(f"mismatches={mism}")
print(f"DEDGES_GOLDEN {hashlib.sha256(blob).hexdigest()}")
