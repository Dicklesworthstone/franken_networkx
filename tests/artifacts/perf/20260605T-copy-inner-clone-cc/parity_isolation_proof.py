import franken_networkx as fnx, networkx as nx, hashlib, json, random
def full_sig(G):
    return json.dumps({
        "nodes": list(G.nodes()),
        "node_data": [(n, sorted(d.items())) for n,d in G.nodes(data=True)],
        "edges": [(u,v) for u,v in G.edges()],
        "edge_data": [(u,v,sorted(d.items())) for u,v,d in G.edges(data=True)],
        "graph_attrs": sorted(G.graph.items()),
        "directed": G.is_directed(),
    }, default=str)

mism=0; sigs=[]
def check(label, Gf):
    global mism
    c = Gf.copy()
    # 1. copy must equal original exactly (nodes+order, edges+order, all attrs)
    if full_sig(c) != full_sig(Gf):
        mism+=1; print(f"COPY!=ORIG {label}")
        # show first node-order diff
        if list(c.nodes())!=list(Gf.nodes()): print("  node order differs")
        if list(c.edges())!=list(Gf.edges()): print("  edge order differs")
    # 2. independence: mutating copy must not affect original
    sig_before = full_sig(Gf)
    nodes=list(c.nodes())
    if nodes:
        c.add_node("ZZZ_new"); 
        c.nodes[nodes[0]]["__probe__"]=1
        if len(list(c.edges())): 
            u,v=next(iter(c.edges())); c[u][v]["__eprobe__"]=2
    if full_sig(Gf)!=sig_before:
        mism+=1; print(f"MUTATION LEAKED to original {label}")
    sigs.append(full_sig(Gf))

# Build a variety of graphs (with attrs, post-creation mutations, str+int nodes)
rng=random.Random(3)
for directed in [False, True]:
    for n,m in [(0,0),(1,0),(20,40),(80,200),(200,600)]:
        Gn = nx.gnm_random_graph(n,m,seed=n+m,directed=directed) if n else (nx.DiGraph() if directed else nx.Graph())
        Gf = (fnx.DiGraph() if directed else fnx.Graph())
        Gf.add_nodes_from(range(n))
        for u,v in (Gn.edges() if n else []):
            w=rng.random(); Gf.add_edge(u,v,weight=w,color="r")
        Gf.graph["gkey"]="gval"
        # post-creation mutations (exercise dirty + node-attr staleness paths)
        if n>2:
            Gf.nodes[0]["nattr"]=99
            ed=list(Gf.edges())
            if ed: u,v=ed[0]; Gf[u][v]["mut"]=7
        check(f"d={directed} n={n} m={m}", Gf)
# string-keyed
Gs=fnx.Graph(); Gs.add_edge("a","b",weight=1); Gs.add_edge("b","c"); Gs.nodes["a"]["x"]=5
check("str_nodes", Gs)

print(f"\nCASES={len(sigs)} MISMATCH={mism}")
print("GOLDEN_SHA256", hashlib.sha256("\n".join(sigs).encode()).hexdigest())
