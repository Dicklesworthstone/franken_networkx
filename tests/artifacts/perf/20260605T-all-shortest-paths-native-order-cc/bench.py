import os, time
for v in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']: os.environ[v]='2'
import networkx as nx, franken_networkx as fnx
def warm_min(fn, reps=12):
    ts=[]
    for _ in range(reps):
        t=time.perf_counter(); fn(); ts.append(time.perf_counter()-t)
    return min(ts)
for n in (1000, 2000, 5000):
    Gfx = fnx.connected_watts_strogatz_graph(n,6,0.2,seed=3)
    Gnx = nx.connected_watts_strogatz_graph(n,6,0.2,seed=3)
    s,t=0,n//2
    tf=warm_min(lambda: list(fnx.all_shortest_paths(Gfx,s,t)))
    tn=warm_min(lambda: list(nx.all_shortest_paths(Gnx,s,t)))
    print(f"n={n}: fnx {tf*1000:.3f}ms  nx {tn*1000:.3f}ms  ratio {tf/tn:.2f}x")
