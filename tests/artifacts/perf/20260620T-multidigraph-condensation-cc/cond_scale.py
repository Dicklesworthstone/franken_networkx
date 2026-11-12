import time, random, networkx as nx, franken_networkx as fnx
def best(fn, reps=9):
    for _ in range(3): fn()
    return min((lambda: (t0:=time.perf_counter(), fn(), time.perf_counter()-t0)[2])() for _ in range(reps))
def mk(cls,n,m,seed=5):
    g=cls(); rnd=random.Random(seed)
    for _ in range(m):
        u,v=rnd.randrange(n),rnd.randrange(n); g.add_edge(u,v)
    return g
for (n,m) in [(1500,6000),(2500,10000),(4000,16000),(4000,4000),(4000,40000)]:
    mf=mk(fnx.MultiDiGraph,n,m); mn=mk(nx.MultiDiGraph,n,m)
    nscc=nx.number_strongly_connected_components(mn)
    bf=best(lambda:fnx.condensation(mf)); bn=best(lambda:nx.condensation(mn))
    print(f"n={n} m={m} #scc={nscc:5d}  fnx {bf*1000:7.2f}ms nx {bn*1000:7.2f}ms {bn/bf:5.2f}x")
