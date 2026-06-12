import franken_networkx as fnx, networkx as nx, random, hashlib, sys, time
tag=sys.argv[1] if len(sys.argv)>1 else "AFTER"
def gsig(G):
    nodes=[(repr(n), tuple(sorted((repr(k),repr(v)) for k,v in d.items()))) for n,d in G.nodes(data=True)]
    return (nodes, list(G.edges()), tuple(sorted((repr(k),repr(v)) for k,v in G.graph.items())), G.is_directed(), G.is_multigraph())
mism=0; total=0; sigs=[]
def build(kind, seed):
    r=random.Random(seed)
    if kind=="simple_int": G=nx.gnp_random_graph(40,0.1,seed=seed)
    elif kind=="attrs":
        G=nx.gnp_random_graph(30,0.1,seed=seed)
        for n in G.nodes(): G.nodes[n]['c']=r.choice('xy'); G.nodes[n]['w']=r.random()
    elif kind=="str_nodes":
        G=nx.Graph(); G.add_nodes_from([f"n{i}" for i in range(25)])
        for _ in range(30): G.add_edge(f"n{r.randrange(25)}",f"n{r.randrange(25)}")
    elif kind=="directed": G=nx.gnp_random_graph(25,0.1,seed=seed,directed=True)
    elif kind=="multi":
        G=nx.MultiGraph(); 
        for _ in range(30): G.add_edge(r.randrange(15),r.randrange(15))
        for n in G.nodes(): G.nodes[n]['z']=r.randint(0,3)
    G.graph['gname']='g'+str(seed)
    return G
fcls={"simple_int":fnx.Graph,"attrs":fnx.Graph,"str_nodes":fnx.Graph,"directed":fnx.DiGraph,"multi":fnx.MultiGraph}
for kind in ["simple_int","attrs","str_nodes","directed","multi"]:
    for seed in range(8):
        G=build(kind,seed); Gf=fcls[kind](G)
        for wd in [True,False]:
            Rx=nx.create_empty_copy(G,with_data=wd); Rf=fnx.create_empty_copy(Gf,with_data=wd)
            total+=1
            sx=gsig(Rx); sf=gsig(Rf)
            if tag=="AFTER": sigs.append(repr(sf))
            if sx!=sf:
                mism+=1
                if mism<=4: print(f"MISMATCH {kind} wd={wd}: nx={str(sx)[:70]} fnx={str(sf)[:70]}")
print(f"[{tag}] total {total} mismatches {mism}")
if tag=="AFTER":
    print("golden sha:", hashlib.sha256("|".join(sigs).encode()).hexdigest()[:16])
    # verify no aliasing: mutate H attr, ensure G unaffected
    G=fnx.gnp_random_graph(10,0.3,seed=1); G.nodes[0]['c']='r'
    H=fnx.create_empty_copy(G); H.nodes[0]['c']='CHANGED'
    print("no aliasing:", G.nodes[0]['c']=='r')
def wm(fn,N,reps=7):
    for _ in range(2):fn()
    b=1e18
    for _ in range(reps):
        t=time.perf_counter()
        for _ in range(N):fn()
        b=min(b,(time.perf_counter()-t)/N)
    return b
for n,N in [(400,200),(1500,60),(40,500)]:
    G=nx.barabasi_albert_graph(n,4,seed=1); Gf=fnx.Graph(G)
    tf=wm(lambda:fnx.create_empty_copy(Gf),N); tx=wm(lambda:nx.create_empty_copy(G),N)
    print(f"[{tag}] BA({n}): fnx={tf*1e3:7.3f}ms nx={tx*1e3:7.3f}ms nx/fnx={tx/tf:.2f}x")
