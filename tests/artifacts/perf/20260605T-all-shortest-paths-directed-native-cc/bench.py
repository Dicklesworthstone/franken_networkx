import os, time
for v in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']: os.environ[v]='2'
import networkx as nx, franken_networkx as fnx
def wm(fn,reps=12):
    ts=[]
    for _ in range(reps):
        t=time.perf_counter(); fn(); ts.append(time.perf_counter()-t)
    return min(ts)
for n in (1000,3000):
    G=nx.gnp_random_graph(n, 6.0/n, seed=5, directed=True)
    F=fnx.DiGraph(); F.add_nodes_from(G.nodes()); F.add_edges_from(G.edges())
    # pick a reachable pair
    import networkx as _nx
    s=0
    t=None
    for cand in range(1,n):
        if _nx.has_path(G,s,cand) and _nx.shortest_path_length(G,s,cand)>=3: t=cand; break
    if t is None: t=n-1
    tf=wm(lambda: list(fnx.all_shortest_paths(F,s,t)))
    tn=wm(lambda: list(nx.all_shortest_paths(G,s,t)))
    print(f"directed n={n} pair({s},{t}): fnx {tf*1000:.3f}ms nx {tn*1000:.3f}ms ratio {tf/tn:.2f}x")
