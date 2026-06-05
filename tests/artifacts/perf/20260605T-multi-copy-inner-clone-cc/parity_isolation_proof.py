import franken_networkx as fnx, networkx as nx, hashlib, json, random
def full_sig(G):
    return json.dumps({
        "nodes": list(G.nodes()),
        "node_data": [(n, sorted(d.items())) for n,d in G.nodes(data=True)],
        "edges_keys": [(u,v,k) for u,v,k in G.edges(keys=True)],
        "edge_data": [(u,v,k,sorted(d.items())) for u,v,k,d in G.edges(keys=True,data=True)],
        "graph_attrs": sorted(G.graph.items()),
        "directed": G.is_directed(),
    }, default=str)
mism=0; sigs=[]
def check(label, Gf):
    global mism
    c = Gf.copy()
    if full_sig(c) != full_sig(Gf):
        mism+=1; print(f"COPY!=ORIG {label}")
        if list(c.nodes())!=list(Gf.nodes()): print("  node order differs:", list(c.nodes())[:8], "vs", list(Gf.nodes())[:8])
        if list(c.edges(keys=True))!=list(Gf.edges(keys=True)): print("  edge/key order differs")
    # deep-copy isolation
    before = full_sig(Gf)
    nodes=list(c.nodes())
    if nodes:
        c.add_node("ZZZ"); c.nodes[nodes[0]]["__p__"]=1
        ed=list(c.edges(keys=True))
        if ed: u,v,k=ed[0]; c[u][v][k]["__e__"]=2; c.add_edge(u,v)  # add parallel edge
    if full_sig(Gf)!=before:
        mism+=1; print(f"MUTATION LEAKED {label}")
    sigs.append(full_sig(Gf))

rng=random.Random(5)
for directed in [False,True]:
    Mk = (fnx.MultiDiGraph if directed else fnx.MultiGraph)
    Mn = (nx.MultiDiGraph if directed else nx.MultiGraph)
    for n,m in [(0,0),(1,0),(15,30),(60,150)]:
        Gn=Mn(); Gf=Mk(); Gf.add_nodes_from(range(n)); Gn.add_nodes_from(range(n))
        for _ in range(m):
            u=rng.randrange(max(n,1)); v=rng.randrange(max(n,1))
            if u==v and n>1: continue
            kf=Gf.add_edge(u,v,weight=rng.random()); 
            # mirror in nx with same key
            Gn.add_edge(u,v,key=kf,weight=1)
        # parallel edges + explicit keys
        if n>3:
            Gf.add_edge(0,1,key="custom",label="x"); Gn.add_edge(0,1,key="custom",label="x")
            Gf.add_edge(0,1,weight=9); Gn.add_edge(0,1,weight=9)
            Gf.nodes[0]["nattr"]=7
        Gf.graph["gk"]="gv"
        check(f"d={directed} n={n} m={m}", Gf)
        # nx parity: node+edge+key order after copy must match nx copy
        cf=Gf.copy(); cn=Gn.copy()
        if list(cf.nodes())!=list(cn.nodes()): mism+=1; print(f"NXPARITY nodeorder d={directed} n={n}")
        if list(cf.edges(keys=True))!=list(cn.edges(keys=True)): mism+=1; print(f"NXPARITY edgeorder d={directed} n={n}")
print(f"\nCASES={len(sigs)} MISMATCH={mism}")
print("GOLDEN_SHA256", hashlib.sha256("\n".join(sigs).encode()).hexdigest())
