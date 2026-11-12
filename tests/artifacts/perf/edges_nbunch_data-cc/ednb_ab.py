import franken_networkx as fnx, networkx as nx, time, sys, hashlib, random
tag=sys.argv[1]
def wm(fn,N=20,reps=7):
    for _ in range(2):fn()
    b=1e18
    for _ in range(reps):
        t=time.perf_counter()
        for _ in range(N):fn()
        b=min(b,(time.perf_counter()-t)/N)
    return b
G=nx.barabasi_albert_graph(300,4,seed=1); Gf=fnx.Graph(G); nb=list(range(150))
print(f"[{tag}] attrless edges(150,data=True): fnx={wm(lambda:list(Gf.edges(nb,data=True)))*1e3:.3f}ms")
Gw=nx.barabasi_albert_graph(300,4,seed=1)
for u,v in Gw.edges(): Gw[u][v]['weight']=(u+v)%9+1
Gwf=fnx.Graph(); Gwf.add_nodes_from(Gw.nodes()); Gwf.add_edges_from((u,v,d) for u,v,d in Gw.edges(data=True))
print(f"[{tag}] attr edges(150,data=weight): fnx={wm(lambda:list(Gwf.edges(nb,data='weight')))*1e3:.3f}ms")
# small nbunch (heuristic -> AtlasView path)
print(f"[{tag}] small nb=[0,1,2] data=True: fnx={wm(lambda:list(Gf.edges([0,1,2],data=True)),N=200)*1e3:.4f}ms")
if tag=="AFTER":
    sigs=[]
    for seed in range(6):
        r=random.Random(seed); edges=[]
        while len(edges)<100:
            a,b=r.randrange(50),r.randrange(50)
            if a!=b: edges.append((a,b,{'w':r.randint(1,9)}))
        g=fnx.Graph(); g.add_nodes_from(range(50)); g.add_edges_from(edges)
        for nbb in [range(25),[0,1],range(50)]:
            for d in [True,False,'w',None]:
                sigs.append(repr(list(g.edges(list(nbb),data=d))))
    print('golden:', hashlib.sha256('|'.join(sigs).encode()).hexdigest()[:16])
