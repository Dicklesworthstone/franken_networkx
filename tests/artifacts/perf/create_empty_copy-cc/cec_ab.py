import franken_networkx as fnx, networkx as nx, time, sys
tag=sys.argv[1]
def wm(fn,N,reps=9):
    for _ in range(3):fn()
    b=1e18
    for _ in range(reps):
        t=time.perf_counter()
        for _ in range(N):fn()
        b=min(b,(time.perf_counter()-t)/N)
    return b
for n,N in [(400,200),(1500,80)]:
    G=nx.barabasi_albert_graph(n,4,seed=1); Gf=fnx.Graph(G)
    tf=wm(lambda:fnx.create_empty_copy(Gf),N); tx=wm(lambda:nx.create_empty_copy(G),N)
    print(f"[{tag}] BA({n}): fnx={tf*1e3:7.3f}ms nx={tx*1e3:7.3f}ms nx/fnx={tx/tf:.2f}x")
