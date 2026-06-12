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
for n,m,N in [(300,4,20),(800,5,10),(1500,4,6)]:
    G=nx.barabasi_albert_graph(n,m,seed=1); Gf=fnx.Graph(G)
    tf=wm(lambda:fnx.contracted_nodes(Gf,0,1),N)
    tx=wm(lambda:nx.contracted_nodes(G,0,1),N)
    print(f"[{tag}] BA({n},{m}): fnx={tf*1e3:7.3f}ms nx={tx*1e3:7.3f}ms nx/fnx={tx/tf:.2f}x")
