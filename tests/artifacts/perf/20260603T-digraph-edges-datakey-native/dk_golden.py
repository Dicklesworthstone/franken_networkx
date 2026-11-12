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
        else: g.add_edge(u,v)  # no w -> default
    return g
mism=0; records=[]
for seed in (1,2,3,4):
    for sl in (True,False):
        gf=build(fnx.DiGraph,seed,sl=sl); gn=build(nx.DiGraph,seed,sl=sl)
        for dk,default in [('w',None),('w',0),('tag','none'),('missing',7)]:
            f=list(gf.edges(data=dk,default=default)); n_=list(gn.edges(data=dk,default=default))
            if f!=n_:
                mism+=1
                for i,(a,b) in enumerate(zip(f,n_)):
                    if a!=b: print(f"  s={seed} sl={sl} dk={dk} def={default} i={i}: fnx={a} nx={b}"); break
            # out_edges(data=str) too
            if list(gf.out_edges(data=dk,default=default))!=list(gn.out_edges(data=dk,default=default)): mism+=1; print(f"  OUT s={seed} dk={dk}")
            records.append([seed,sl,dk,str(default),f])
        # unchanged paths
        if list(gf.edges(data=True))!=list(gn.edges(data=True)): mism+=1; print(f"  data=True regressed s={seed}")
        if list(gf.edges())!=list(gn.edges()): mism+=1; print(f"  nodata regressed s={seed}")
        nb=sorted(random.Random(seed).sample(range(50),10))
        if list(gf.edges(nb,data='w'))!=list(gn.edges(nb,data='w')): mism+=1; print(f"  nbunch data=w s={seed}")
blob=json.dumps(records, sort_keys=True, default=str).encode()
print(f"mismatches={mism}")
print(f"DK_GOLDEN {hashlib.sha256(blob).hexdigest()}")
