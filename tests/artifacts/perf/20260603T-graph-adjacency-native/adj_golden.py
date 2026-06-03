import franken_networkx as fnx, networkx as nx, random, json, hashlib
def build(M, seed, n=30, e=80, sl=True):
    g=M(); r=random.Random(seed)
    for x in [5,2,9,1,7]: g.add_node(x)
    g.add_nodes_from(range(n))
    for _ in range(e):
        u,v=r.randint(0,n-1),r.randint(0,n-1)
        if not sl and u==v: v=(v+1)%n
        k=r.randint(0,2)
        if k==0: g.add_edge(u,v,weight=round(r.random(),3))
        elif k==1: g.add_edge(u,v,weight=r.randint(1,9),tag="a")
        else: g.add_edge(u,v)
    return g
mism=0; records=[]
for label,Mf,Mn in [("Graph",fnx.Graph,nx.Graph),("DiGraph",fnx.DiGraph,nx.DiGraph)]:
    for seed in (1,2,3,4):
        for sl in (True,False):
            gf=build(Mf,seed,sl=sl); gn=build(Mn,seed,sl=sl)
            af=[(nd, dict(a)) for nd,a in gf.adjacency()]
            an=[(nd, dict(a)) for nd,a in gn.adjacency()]
            if af != an:
                mism+=1
                for i,(x,y) in enumerate(zip(af,an)):
                    if x!=y: print(f"  ADJ {label} s={seed} sl={sl} i={i}: fnx={str(x)[:60]} nx={str(y)[:60]}"); break
            records.append([label,seed,sl,[(nd, list(a.keys())) for nd,a in af]])
        # shared-datadict identity: dict(G.adjacency())[u][v] is G[u][v]
        gf=build(Mf,seed); 
        adj=dict(gf.adjacency())
        for u,v in list(gf.edges())[:5]:
            assert adj[u][v] is gf[u][v], f"identity fail {label} {u},{v}"
        # mutation visibility (snapshot reuses live dict)
        u,v=list(gf.edges())[0]
        adj2=dict(gf.adjacency()); adj2[u][v]["zz"]=1
        assert gf[u][v].get("zz")==1, "mutation not visible"; del gf[u][v]["zz"]
        # subgraph view still works (FilterAtlas path)
        sub=sorted(random.Random(seed).sample(range(30),18))
        vf=gf.subgraph(sub); vn=build(Mn,seed).subgraph(sub)
        if [(nd,dict(a)) for nd,a in vf.adjacency()]!=[(nd,dict(a)) for nd,a in vn.adjacency()]:
            mism+=1; print(f"  SUBGRAPH ADJ {label} s={seed}")
blob=json.dumps(records, sort_keys=True).encode()
print(f"mismatches={mism}")
print(f"ADJ_GOLDEN {hashlib.sha256(blob).hexdigest()}")
