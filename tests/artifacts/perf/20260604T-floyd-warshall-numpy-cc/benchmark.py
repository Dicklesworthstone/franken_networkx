import franken_networkx as fnx
import networkx as nx
import random, time

def build(n, p, seed, weighted=True):
    rng = random.Random(seed)
    Gn = nx.gnp_random_graph(n, p, seed=seed)
    Gf = fnx.Graph(); Gf.add_nodes_from(range(n))
    for u,v in Gn.edges():
        if weighted:
            w = round(rng.uniform(1,10),3)
            Gn[u][v]['weight'] = w
            Gf.add_edge(u,v,weight=w)
        else:
            Gf.add_edge(u,v)
    return Gf, Gn

def bench(fn, *a, reps=5):
    best = float('inf')
    for _ in range(reps):
        t=time.perf_counter(); fn(*a); best=min(best, time.perf_counter()-t)
    return best

for n in [150, 300]:
    Gf, Gn = build(n, 0.1, 7, weighted=True)
    # warm
    fnx.floyd_warshall(Gf); nx.floyd_warshall(Gn)
    tf = bench(lambda: fnx.floyd_warshall(Gf, weight="weight"))
    tn = bench(lambda: nx.floyd_warshall(Gn, weight="weight"))
    print(f"n={n} weighted: fnx={tf*1000:.2f}ms nx={tn*1000:.2f}ms  ratio nx/fnx={tn/tf:.2f}x")
