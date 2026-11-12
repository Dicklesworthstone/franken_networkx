import time, statistics, random
import networkx as nx
import franken_networkx as fnx

def build(mod, n, m, seed):
    rng=random.Random(seed)
    G=mod.Graph(); G.add_nodes_from(range(n))
    while G.number_of_edges()<m:
        u=rng.randrange(n); v=rng.randrange(n)
        if u!=v: G.add_edge(u,v)
    return G

def bench(fn, reps=9):
    ts=[]
    for _ in range(reps):
        t=time.perf_counter(); fn(); ts.append(time.perf_counter()-t)
    return statistics.median(ts)

for (n,m) in [(1500,7500),(2000,12000),(800,8000)]:
    Gn=build(nx,n,m,7); Gf=build(fnx,n,m,7)
    tn=bench(lambda: nx.square_clustering(Gn))
    tf=bench(lambda: fnx.square_clustering(Gf))
    print(f"n={n} m={m}: nx={tn*1e3:8.2f}ms fnx={tf*1e3:8.2f}ms  speedup_vs_nx={tn/tf:6.2f}x")
