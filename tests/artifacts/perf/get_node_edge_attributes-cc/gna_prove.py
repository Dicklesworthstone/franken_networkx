import franken_networkx as fnx, networkx as nx, random, hashlib, sys, time
tag=sys.argv[1] if len(sys.argv)>1 else "AFTER"
def to_nx(G):
    H=(nx.MultiDiGraph if G.is_multigraph() and G.is_directed() else nx.MultiGraph if G.is_multigraph() else nx.DiGraph if G.is_directed() else nx.Graph)()
    H.add_nodes_from(G.nodes(data=True))
    if G.is_multigraph(): H.add_edges_from(G.edges(keys=True,data=True))
    else: H.add_edges_from(G.edges(data=True))
    return H
mism=0; total=0; sigs=[]
r=random.Random(0)
def mk(kind,seed):
    rr=random.Random(seed)
    cls={"g":fnx.Graph,"d":fnx.DiGraph,"mg":fnx.MultiGraph,"mdg":fnx.MultiDiGraph}[kind]
    G=cls()
    G.add_nodes_from(range(30))
    for _ in range(50):
        a,b=rr.randrange(30),rr.randrange(30)
        if kind in ("mg","mdg"): G.add_edge(a,b)
        else: G.add_edge(a,b)
    return G,rr
configs=[]
for kind in ["g","d","mg","mdg"]:
    for seed in range(6):
        for attrmode in ["none","node","edge","both","partial"]:
            configs.append((kind,seed,attrmode))
for kind,seed,attrmode in configs:
    G,rr=mk(kind,seed)
    if attrmode in ("node","both"):
        for n in list(G.nodes())[:20]: G.nodes[n]['w']=rr.randint(1,9)
    if attrmode in ("edge","both"):
        for e in list(G.edges())[:25]:
            if kind in ("mg","mdg"): G.edges[e[0],e[1],0]['cap']=rr.randint(1,5)
            else: G.edges[e]['cap']=rr.randint(1,5)
    if attrmode=="partial":
        for n in list(G.nodes())[:10]: G.nodes[n]['w']=rr.randint(1,9)
    nxG=to_nx(G)
    for name,dflt in [('w',None),('w',-1),('cap',None),('missing',None),('missing',0)]:
        rn_x=nx.get_node_attributes(nxG,name,default=dflt); rn_f=fnx.get_node_attributes(G,name,default=dflt)
        re_x=nx.get_edge_attributes(nxG,name,default=dflt); re_f=fnx.get_edge_attributes(G,name,default=dflt)
        total+=2
        if rn_x!=rn_f or list(rn_x)!=list(rn_f): mism+=1; (print(f"NODE MISMATCH {kind} {attrmode} {name} d={dflt}: nx={dict(list(rn_x.items())[:2])} fnx={dict(list(rn_f.items())[:2])}") if mism<=5 else None)
        if re_x!=re_f or list(re_x)!=list(re_f): mism+=1; (print(f"EDGE MISMATCH {kind} {attrmode} {name} d={dflt}") if mism<=5 else None)
        if tag=="AFTER": sigs.append(repr((sorted(rn_f.items(),key=repr),sorted(re_f.items(),key=repr))))
print(f"[{tag}] total {total} mismatches {mism}")
if tag=="AFTER": print("golden:", hashlib.sha256("|".join(sigs).encode()).hexdigest()[:16])
