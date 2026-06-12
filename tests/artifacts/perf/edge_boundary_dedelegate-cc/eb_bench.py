import franken_networkx as fnx, networkx as nx, time, sys
tag=sys.argv[1]
def wm(fn,N,reps=7):
    for _ in range(2):fn()
    b=1e18
    for _ in range(reps):
        t=time.perf_counter()
        for _ in range(N):fn()
        b=min(b,(time.perf_counter()-t)/N)
    return b
for n in [200,500]:
    G=nx.barabasi_albert_graph(n,4,seed=1); Gf=fnx.Graph(G)
    S=set(range(n//2))
    tf=wm(lambda:list(fnx.edge_boundary(Gf,S,data=True)),50)
    tx=wm(lambda:list(nx.edge_boundary(G,S,data=True)),50)
    print(f"[{tag}] BA({n}) data=True: fnx={tf*1e3:.3f}ms nx={tx*1e3:.3f}ms nx/fnx={tx/tf:.2f}x")
