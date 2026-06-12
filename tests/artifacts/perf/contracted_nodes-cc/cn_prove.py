import franken_networkx as fnx, networkx as nx, random, hashlib, sys
tag=sys.argv[1] if len(sys.argv)>1 else "AFTER"
def gsig(G):
    nodes=[(repr(n), tuple(sorted((repr(k),repr(v)) for k,v in d.items()))) for n,d in G.nodes(data=True)]
    if G.is_multigraph():
        edges=[(repr(a),repr(b),repr(k),tuple(sorted((repr(kk),repr(vv)) for kk,vv in d.items()))) for a,b,k,d in G.edges(keys=True,data=True)]
    else:
        edges=[(repr(a),repr(b),tuple(sorted((repr(kk),repr(vv)) for kk,vv in d.items()))) for a,b,d in G.edges(data=True)]
    return (nodes, edges, tuple(sorted((repr(k),repr(v)) for k,v in G.graph.items())))
mism=0; total=0; sigs=[]
def build(kind, seed):
    r=random.Random(seed)
    if kind=="simple": G=nx.gnp_random_graph(20,0.2,seed=seed)
    elif kind=="directed": G=nx.gnp_random_graph(18,0.15,seed=seed,directed=True)
    elif kind=="weighted":
        G=nx.gnp_random_graph(18,0.2,seed=seed)
        for a,b in G.edges(): G[a][b]['weight']=r.randint(1,9)
        for n in G.nodes(): G.nodes[n]['color']=r.choice('rgb')
    elif kind=="multi":
        G=nx.MultiGraph(); 
        for _ in range(40): a,b=r.randrange(15),r.randrange(15); G.add_edge(a,b,weight=r.randint(1,5))
    elif kind=="multidi":
        G=nx.MultiDiGraph()
        for _ in range(40): a,b=r.randrange(12),r.randrange(12); G.add_edge(a,b)
    G.graph['name']='test'+str(seed)
    return G
for kind in ["simple","directed","weighted","multi","multidi"]:
    for seed in range(8):
        G=build(kind,seed)
        nodes=list(G.nodes())
        if len(nodes)<2: continue
        for _ in range(4):
            u,v=random.Random(seed*7+_).sample(nodes,2)
            for sl in [True,False]:
                Gx=nx.Graph(G) if False else G.copy()
                Gf=fnx.from_networkx(G.copy()) if hasattr(fnx,'from_networkx') else fnx.empty_graph(0)
                # build fnx from nx
                Gff = (fnx.MultiDiGraph if kind=="multidi" else fnx.MultiGraph if kind=="multi" else fnx.DiGraph if kind=="directed" else fnx.Graph)(G)
                try: Rx=nx.contracted_nodes(G.copy(),u,v,self_loops=sl)
                except Exception as ex: Rx=("ERR",type(ex).__name__)
                try: Rf=fnx.contracted_nodes(Gff.copy(),u,v,self_loops=sl)
                except Exception as ex: Rf=("ERR",type(ex).__name__)
                total+=1
                sx=gsig(Rx) if not isinstance(Rx,tuple) else Rx
                sf=gsig(Rf) if not isinstance(Rf,tuple) else Rf
                if tag=="AFTER": sigs.append(repr(sf))
                if sx!=sf:
                    mism+=1
                    if mism<=4: print(f"MISMATCH {kind} u={u} v={v} sl={sl}: nx={str(sx)[:80]} fnx={str(sf)[:80]}")
print(f"[{tag}] total {total} mismatches {mism}")
if tag=="AFTER":
    print("golden sha:", hashlib.sha256("|".join(sigs).encode()).hexdigest()[:16])
