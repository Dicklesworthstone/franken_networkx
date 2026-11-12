import os, time
for v in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']: os.environ[v]='2'
import networkx as nx, franken_networkx as fnx
from collections import deque

def warm_min(fn, reps=8):
    ts=[]
    for _ in range(reps):
        t=time.perf_counter(); fn(); ts.append(time.perf_counter()-t)
    return min(ts)

def old_descendants(G, source):  # the previous Python-BFS path
    seen={source}; q=deque([source])
    while q:
        n=q.popleft()
        for nbr in G[n]:
            if nbr not in seen:
                seen.add(nbr); q.append(nbr)
    seen.discard(source); return seen

for n in (1000, 3000):
    Gfx = fnx.connected_watts_strogatz_graph(n,6,0.2,seed=3)
    Gnx = nx.connected_watts_strogatz_graph(n,6,0.2,seed=3)
    new = warm_min(lambda: fnx.descendants(Gfx,0))
    old = warm_min(lambda: old_descendants(Gfx,0))
    nxt = warm_min(lambda: nx.descendants(Gnx,0))
    print(f"n={n}: OLD(pyBFS) {old*1000:.3f}ms -> NEW(native) {new*1000:.3f}ms = {old/new:.2f}x self | vs nx {nxt*1000:.3f}ms ratio {new/nxt:.2f}x")
