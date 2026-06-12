import franken_networkx as fnx, networkx as nx, time
def wm(fn,N,reps=7):
    for _ in range(3):fn()
    b=1e18
    for _ in range(reps):
        t=time.perf_counter()
        for _ in range(N):fn()
        b=min(b,(time.perf_counter()-t)/N)
    return b
import sys
mode=sys.argv[1]
for n,k in [(600,3),(2000,5),(5000,10),(2000,50)]:
    G=nx.barabasi_albert_graph(n,4,seed=1); Gf=fnx.Graph(G)
    centers=set(range(0,n,max(1,n//k)))[:k] if False else set(list(range(k)))
    N=max(5, 200//(n//500+1))
    tf=wm(lambda:fnx.voronoi_cells(Gf,centers),N)
    tx=wm(lambda:nx.voronoi_cells(G,centers),N)
    print(f"[{mode}] n={n:5d} k={len(centers):3d}: fnx={tf*1e3:7.3f}ms nx={tx*1e3:7.3f}ms  nx/fnx={tx/tf:.2f}x")
