import time, random
import networkx as nx
import franken_networkx as fnx

def build(mod, directed, n, m, seed=7):
    rng = random.Random(seed)
    G = (mod.MultiDiGraph if directed else mod.MultiGraph)()
    for i in range(n): G.add_node(str(i))
    for _ in range(m):
        u=str(rng.randrange(n)); v=str(rng.randrange(n))
        G.add_edge(u,v)
    return G

def timeit(mod, directed, n, m, iters):
    best=1e9
    for _ in range(3):
        G=build(mod,directed,n,m)
        victims=list(G.nodes())[:iters]
        t=time.perf_counter()
        for nd in victims:
            G.remove_node(nd)
        best=min(best, time.perf_counter()-t)
    return best

for directed in (False, True):
    n,m,iters=1000,8000,500
    fx=timeit(fnx,directed,n,m,iters)
    nxx=timeit(nx,directed,n,m,iters)
    label="MultiDiGraph" if directed else "MultiGraph"
    print(f"{label} remove_node x{iters}: fnx {fx*1000:.2f}ms  nx {nxx*1000:.2f}ms  ratio {fx/nxx:.2f}x")
