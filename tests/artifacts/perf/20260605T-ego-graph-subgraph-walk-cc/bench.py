import os, time
for v in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']: os.environ[v]='2'
import networkx as nx, franken_networkx as fnx
def warm_min(fn, reps=10):
    ts=[]
    for _ in range(reps):
        t=time.perf_counter(); fn(); ts.append(time.perf_counter()-t)
    return min(ts)
for n,r in ((2000,2),(5000,2),(2000,3)):
    Gfx = fnx.connected_watts_strogatz_graph(n,6,0.2,seed=3)
    Gnx = nx.connected_watts_strogatz_graph(n,6,0.2,seed=3)
    tf = warm_min(lambda: fnx.ego_graph(Gfx,0,radius=r))
    tn = warm_min(lambda: nx.ego_graph(Gnx,0,radius=r))
    print(f"n={n} r={r}: fnx {tf*1000:.3f}ms  nx {tn*1000:.3f}ms  ratio {tf/tn:.2f}x")
