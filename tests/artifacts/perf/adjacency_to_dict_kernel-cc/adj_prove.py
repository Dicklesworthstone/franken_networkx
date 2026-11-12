import franken_networkx as fnx, networkx as nx, random, hashlib, sys, time
tag=sys.argv[1] if len(sys.argv)>1 else "AFTER"
def to_nx(G):
    H=(nx.DiGraph if G.is_directed() else nx.Graph)()
    H.add_nodes_from(G.nodes(data=True)); H.add_edges_from(G.edges(data=True)); return H
mism=0; total=0; sigs=[]
for kind in ["g","d"]:
    for seed in range(8):
        r=random.Random(seed)
        G=(fnx.DiGraph if kind=="d" else fnx.Graph)()
        G.add_nodes_from(range(40))
        for _ in range(80):
            a,b=r.randrange(40),r.randrange(40)
            if a!=b: G.add_edge(a,b)
        if seed%2: 
            for e in list(G.edges())[:30]: G[e[0]][e[1]]['w']=r.randint(1,9)
        nxG=to_nx(G)
        adj_f=dict(G.adjacency()); adj_x=dict(nxG.adjacency())
        total+=1
        # structure + order
        if adj_f!=adj_x or list(adj_f)!=list(adj_x) or any(list(adj_f[k])!=list(adj_x[k]) for k in adj_f):
            mism+=1
            if mism<=4: print(f"MISMATCH {kind} seed{seed}: eq={adj_f==adj_x}")
        if tag=="AFTER":
            sigs.append(repr([(k, list(adj_f[k].items())) for k in adj_f]))
        # live mutation still works (identity)
        if G.number_of_edges()>0:
            u=next(iter(adj_f)); 
            if adj_f[u]:
                v=next(iter(adj_f[u]))
                if adj_f[u][v] is not G[u][v]: mism+=1; (print(f"IDENTITY BROKEN {kind} seed{seed}") if mism<=4 else None)
print(f"[{tag}] total {total} mismatches {mism}")
if tag=="AFTER": print("golden:", hashlib.sha256("|".join(sigs).encode()).hexdigest()[:16])
# bench
def wm(fn,N,reps=7):
    for _ in range(2):fn()
    b=1e18
    for _ in range(reps):
        t=time.perf_counter()
        for _ in range(N):fn()
        b=min(b,(time.perf_counter()-t)/N)
    return b
for n in [400,800,1500]:
    G=nx.barabasi_albert_graph(n,4,seed=1); Gf=fnx.Graph(G)
    tf=wm(lambda:dict(Gf.adjacency()),100); tx=wm(lambda:dict(G.adjacency()),100)
    print(f"[{tag}] BA({n}): fnx={tf*1e3:.4f}ms nx={tx*1e3:.4f}ms nx/fnx={tx/tf:.2f}x")
