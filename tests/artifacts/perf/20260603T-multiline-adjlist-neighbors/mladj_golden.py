import franken_networkx as fnx, networkx as nx, random, json, hashlib, tempfile
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
            for delim in (" ","|"):
                gf=build(Mf,seed,sl=sl); gn=build(Mn,seed,sl=sl)
                f=list(fnx.generate_multiline_adjlist(gf,delim)); n_=list(nx.generate_multiline_adjlist(gn,delim))
                if f!=n_: mism+=1; print(f"  MLADJ {label} s={seed} sl={sl} d={delim!r}")
                records.append([label,seed,sl,delim,f])
        # subgraph view
        gf=build(Mf,seed); gn=build(Mn,seed)
        sub=sorted(random.Random(seed).sample(range(30),20))
        if list(fnx.generate_multiline_adjlist(gf.subgraph(sub)))!=list(nx.generate_multiline_adjlist(gn.subgraph(sub))):
            mism+=1; print(f"  SUBGRAPH MLADJ {label} s={seed}")
# write_multiline_adjlist roundtrip body parity if available
try:
    td=tempfile.mkdtemp()
    g=build(fnx.Graph,7); gn=build(nx.Graph,7)
    fnx.write_multiline_adjlist(g, td+"/f"); nx.write_multiline_adjlist(gn, td+"/n")
    bf=open(td+"/f").read().split("\n",1)[1]; bn=open(td+"/n").read().split("\n",1)[1]
    if bf!=bn: mism+=1; print("  write_multiline body mismatch")
except Exception as e: print("  (write roundtrip skipped:", str(e)[:40],")")
blob=json.dumps(records, sort_keys=True).encode()
print(f"mismatches={mism}")
print(f"MLADJ_GOLDEN {hashlib.sha256(blob).hexdigest()}")
