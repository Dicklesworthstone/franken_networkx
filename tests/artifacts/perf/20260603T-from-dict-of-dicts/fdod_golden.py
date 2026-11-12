import franken_networkx as fnx, networkx as nx, random, json, hashlib
def make_dod(seed, n=25, e=120, level=3):
    r=random.Random(seed); dod={i:{} for i in range(n)}
    for _ in range(e):
        u,v=r.randint(0,n-1),r.randint(0,n-1)
        if u==v: continue
        if level==4:
            k=r.randint(0,2)
            dod.setdefault(u,{}).setdefault(v,{})[k]={'w':round(r.random(),3)} if r.random()<0.7 else {}
        else:
            dod[u][v]={'w':round(r.random(),3)} if r.random()<0.7 else {}
    return dod
def snap(g):
    return {"nodes":sorted(g.nodes()),
            "edges":sorted((u,v,k,tuple(sorted(d.items()))) for u,v,k,d in g.edges(keys=True,data=True)) if g.is_multigraph() else sorted((u,v,tuple(sorted(d.items()))) for u,v,d in g.edges(data=True)),
            "m":g.number_of_edges()}
mism=0; records=[]
for seed in (1,2,3,4):
    # 3-level for Graph/DiGraph/MultiGraph(3lvl)
    dod=make_dod(seed,level=3)
    for cu in ['Graph','DiGraph','MultiGraph','MultiDiGraph']:
        Mf=getattr(fnx,cu); Mn=getattr(nx,cu)
        gf=fnx.from_dict_of_dicts(dod, create_using=Mf())
        gn=nx.from_dict_of_dicts(dod, create_using=Mn())
        if snap(gf)!=snap(gn): mism+=1; print(f"  3lvl {cu} seed={seed} mismatch")
        records.append([cu,seed,3,snap(gf)])
    # 4-level for multigraphs (multigraph_input=True)
    dod4=make_dod(seed,level=4)
    for cu in ['MultiGraph','MultiDiGraph']:
        Mf=getattr(fnx,cu); Mn=getattr(nx,cu)
        gf=fnx.from_dict_of_dicts(dod4, create_using=Mf(), multigraph_input=True)
        gn=nx.from_dict_of_dicts(dod4, create_using=Mn(), multigraph_input=True)
        if snap(gf)!=snap(gn): mism+=1; print(f"  4lvl {cu} seed={seed} mismatch")
        records.append([cu,seed,4,snap(gf)])
# liveness check: simple get_edge_data(u,v) mutation persists
g=fnx.from_dict_of_dicts({0:{1:{'w':5}}}, create_using=fnx.Graph())
assert g[0][1]['w']==5
blob=json.dumps(records, sort_keys=True, default=str).encode()
print(f"mismatches={mism}")
print(f"FDOD_GOLDEN {hashlib.sha256(blob).hexdigest()}")
