import franken_networkx as fnx, networkx as nx, time, sys
def wm(fn,N,reps=7):
    for _ in range(2):fn()
    b=1e18
    for _ in range(reps):
        t=time.perf_counter()
        for _ in range(N):fn()
        b=min(b,(time.perf_counter()-t)/N)
    return b
tag=sys.argv[1]
for n,m,N in [(400,4,20),(800,4,10),(1500,4,5)]:
    G=nx.barabasi_albert_graph(n,m,seed=1); Gf=fnx.Graph(G)
    tf=wm(lambda:fnx.line_graph(Gf),N); tx=wm(lambda:nx.line_graph(G),N)
    print(f"[{tag}] BA({n},{m}): fnx={tf*1e3:7.2f}ms nx={tx*1e3:7.2f}ms  nx/fnx={tx/tf:.2f}x")
