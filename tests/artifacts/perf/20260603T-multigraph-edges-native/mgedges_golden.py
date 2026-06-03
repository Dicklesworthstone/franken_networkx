import franken_networkx as fnx, networkx as nx, random, json, hashlib
def build(M, seed, n=40, e=110, sl=True):
    g=M(); r=random.Random(seed)
    for x in [9,2,5,1,7]: g.add_node(x)
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
        gf=build(fnx.MultiGraph,seed,sl=sl); gn=build(nx.MultiGraph,seed,sl=sl)
        cases=[
            ("edges", lambda g: list(g.edges())),
            ("edges(keys)", lambda g: list(g.edges(keys=True))),
            ("edges(data)", lambda g: list(g.edges(data=True))),
            ("edges(data,keys)", lambda g: list(g.edges(data=True,keys=True))),
            ("edges(data=w)", lambda g: list(g.edges(data='w'))),
            ("edges(data=w,keys)", lambda g: list(g.edges(data='w',keys=True))),
            ("edges(data=miss,def7)", lambda g: list(g.edges(data='zz',default=7))),
        ]
        for desc, fn in cases:
            f=fn(gf); n_=fn(gn)
            if f!=n_:
                mism+=1
                for i,(a,b) in enumerate(zip(f,n_)):
                    if a!=b: print(f"  {desc} s={seed} sl={sl} i={i}: fnx={a} nx={b}"); break
                if len(f)!=len(n_): print(f"  {desc} LEN fnx={len(f)} nx={len(n_)}")
            records.append([seed,sl,desc,[list(t) if isinstance(t,tuple) else t for t in f]])
        # identity for data=True
        ed=list(gf.edges(data=True,keys=True))
        for u,v,k,d in ed[:5]:
            assert d is gf[u][v][k], f"identity {u},{v},{k}"
        # type names
        assert type(gf.edges(data=True)).__name__==type(gn.edges(data=True)).__name__, "type data"
        assert type(gf.edges(keys=True)).__name__==type(gn.edges(keys=True)).__name__, "type keys"
        # nbunch path
        nb=sorted(random.Random(seed).sample(range(40),12))
        if list(gf.edges(nb,data=True))!=list(gn.edges(nb,data=True)): mism+=1; print(f"  nbunch s={seed}")
blob=json.dumps(records, sort_keys=True, default=str).encode()
print(f"mismatches={mism}")
print(f"MGEDGES_GOLDEN {hashlib.sha256(blob).hexdigest()}")
