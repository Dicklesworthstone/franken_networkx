import franken_networkx as fnx, networkx as nx, random, json, hashlib
def gen(M, eb, gattr=None):
    g=M()
    if gattr: g.add_edges_from(eb, **gattr)
    else: g.add_edges_from(eb)
    return g
mism=0; records=[]
for seed in (1,2,3,4):
    r=random.Random(seed); eb=[]
    for _ in range(400):
        u,v=r.randint(0,20),r.randint(0,20); c=r.randint(0,4)
        if c==0: eb.append((u,v))
        elif c==1: eb.append((u,v,{'w':round(r.random(),3)}))
        elif c==2: eb.append((u,v,r.randint(3,7)))           # explicit key
        elif c==3: eb.append((u,v,r.randint(3,7),{'t':'x'})) # 4-tuple
        else: eb.append((u,v,{'key':99,'w':1}))              # 'key' attr collision test
    for gattr in (None, {'color':'red'}):
        for label,Mf,Mn in [("MultiGraph",fnx.MultiGraph,nx.MultiGraph),("MultiDiGraph",fnx.MultiDiGraph,nx.MultiDiGraph)]:
            gf=gen(Mf,eb,gattr); gn=gen(Mn,eb,gattr)
            fe=sorted((u,v,k,tuple(sorted(d.items()))) for u,v,k,d in gf.edges(keys=True,data=True))
            ne=sorted((u,v,k,tuple(sorted(d.items()))) for u,v,k,d in gn.edges(keys=True,data=True))
            if fe!=ne:
                mism+=1
                for a,b in zip(fe,ne):
                    if a!=b: print(f"  {label} seed={seed} gattr={gattr}: {a} vs {b}"); break
                if len(fe)!=len(ne): print(f"  LEN fnx={len(fe)} nx={len(ne)}")
            # attr-persistence (get_edge_data is live): mutate via the returned dict
            records.append([label,seed,str(gattr),fe])
# attr-persistence direct check
g=fnx.MultiGraph(); g.add_edges_from([(0,1,{'w':5})])
assert g.get_edge_data(0,1,0) is g[0][1][0], "get_edge_data must be live"
assert g[0][1][0]['w']==5, "attr must persist"
blob=json.dumps(records, sort_keys=True, default=str).encode()
print(f"mismatches={mism}")
print(f"MGADD_GOLDEN {hashlib.sha256(blob).hexdigest()}")
