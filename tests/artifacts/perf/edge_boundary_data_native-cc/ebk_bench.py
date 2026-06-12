import franken_networkx as fnx, networkx as nx, time, sys
tag=sys.argv[1]
def wm(fn,N=50,reps=7):
    for _ in range(2):fn()
    b=1e18
    for _ in range(reps):
        t=time.perf_counter()
        for _ in range(N):fn()
        b=min(b,(time.perf_counter()-t)/N)
    return b
# attr-less
for n in [200,500]:
    G=nx.barabasi_albert_graph(n,4,seed=1); Gf=fnx.Graph(G); S=set(range(n//2))
    tf=wm(lambda:list(fnx.edge_boundary(Gf,S,data=True))); tx=wm(lambda:list(nx.edge_boundary(G,S,data=True)))
    print(f"[{tag}] BA({n}) attrless data=True: fnx={tf*1e3:.3f}ms nx={tx*1e3:.3f}ms nx/fnx={tx/tf:.2f}x")
# attr-present
G=nx.barabasi_albert_graph(500,4,seed=1)
for u,v in G.edges(): G[u][v]['weight']=(u+v)%9+1
Gf=fnx.Graph(); Gf.add_nodes_from(G.nodes()); Gf.add_edges_from((u,v,d) for u,v,d in G.edges(data=True)); S=set(range(250))
tf=wm(lambda:list(fnx.edge_boundary(Gf,S,data='weight'))); tx=wm(lambda:list(nx.edge_boundary(G,S,data='weight')))
print(f"[{tag}] BA(500) attr data=weight: fnx={tf*1e3:.3f}ms nx={tx*1e3:.3f}ms nx/fnx={tx/tf:.2f}x")
