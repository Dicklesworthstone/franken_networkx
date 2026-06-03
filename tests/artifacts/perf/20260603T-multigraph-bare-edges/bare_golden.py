import franken_networkx as fnx, networkx as nx, random, json, hashlib
def build(M, seed, n=40, e=110, sl=True):
    g=M(); r=random.Random(seed)
    for x in [9,2,5,1,7]: g.add_node(x)
    g.add_nodes_from(range(n))
    for _ in range(e):
        u,v=r.randint(0,n-1),r.randint(0,n-1)
        if not sl and u==v: v=(v+1)%n
        g.add_edge(u,v,w=round(r.random(),3))
    return g
mism=0; records=[]
for seed in (1,2,3,4):
    for sl in (True,False):
        gf=build(fnx.MultiGraph,seed,sl=sl); gn=build(nx.MultiGraph,seed,sl=sl)
        f=list(gf.edges()); n_=list(gn.edges())
        if f!=n_:
            mism+=1
            for i,(a,b) in enumerate(zip(f,n_)):
                if a!=b: print(f"  bare edges() s={seed} sl={sl} i={i}: fnx={a} nx={b}"); break
            if len(f)!=len(n_): print(f"  LEN fnx={len(f)} nx={len(n_)}")
        # len + containment + set algebra still work
        assert len(gf.edges())==len(gn.edges())
        assert ((9,2) in gf.edges())==((9,2) in gn.edges())
        records.append([seed,sl,f])
blob=json.dumps(records, sort_keys=True).encode()
print(f"mismatches={mism}")
print(f"BARE_GOLDEN {hashlib.sha256(blob).hexdigest()}")
