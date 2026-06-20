import time, random, networkx as nx, franken_networkx as fnx
def best(fn, reps=15):
    for _ in range(3): fn()
    return min((lambda: (t0:=time.perf_counter(), fn(), time.perf_counter()-t0)[2])() for _ in range(reps))
def row(name, ff, nf):
    bf,bn=best(ff),best(nf); print(f"{name:34s} fnx {bf*1000:8.3f}ms nx {bn*1000:8.3f}ms {bn/bf:6.2f}x {'WIN' if bn/bf>1.05 else 'LOSS' if bn/bf<0.95 else 'neu'}")
def mk(cls,n,m,seed=2):
    g=cls(); rnd=random.Random(seed)
    for _ in range(m):
        u,v=rnd.randrange(n),rnd.randrange(n)
        if u!=v: g.add_edge(u,v)
    return g
mf=mk(fnx.MultiDiGraph,1500,6000); mn=mk(nx.MultiDiGraph,1500,6000)
row("MDG find_cycle n=1500", lambda:fnx.find_cycle(mf), lambda:nx.find_cycle(mn))
mf2=mk(fnx.MultiDiGraph,5000,20000); mn2=mk(nx.MultiDiGraph,5000,20000)
row("MDG find_cycle n=5000", lambda:fnx.find_cycle(mf2), lambda:nx.find_cycle(mn2))
