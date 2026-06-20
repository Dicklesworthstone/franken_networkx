import time, random, networkx as nx, franken_networkx as fnx
def best(fn, reps=15):
    for _ in range(3): fn()
    return min((lambda: (t0:=time.perf_counter(), fn(), time.perf_counter()-t0)[2])() for _ in range(reps))
def row(name, ff, nf):
    bf,bn=best(ff),best(nf); print(f"{name:36s} fnx {bf*1000:8.3f}ms nx {bn*1000:8.3f}ms {bn/bf:6.2f}x {'WIN' if bn/bf>1.05 else 'LOSS' if bn/bf<0.95 else 'neu'}")
def mk(cls,n,m,seed=1):
    g=cls(); rnd=random.Random(seed)
    for _ in range(m):
        u,v=rnd.randrange(n),rnd.randrange(n)
        if u!=v: g.add_edge(u,v)
    return g
# cycle-dense (early exit)
mf=mk(fnx.MultiGraph,1500,6000); mn=mk(nx.MultiGraph,1500,6000)
row("MG find_cycle (dense, n=1500)", lambda:fnx.find_cycle(mf), lambda:nx.find_cycle(mn))
# larger
mf2=mk(fnx.MultiGraph,5000,20000); mn2=mk(nx.MultiGraph,5000,20000)
row("MG find_cycle (dense, n=5000)", lambda:fnx.find_cycle(mf2), lambda:nx.find_cycle(mn2))
# near-tree (cycle found late / forest) — sparse
def mktree(cls,n):
    g=cls()
    for i in range(1,n): g.add_edge(i,i//2)
    g.add_edge(n-1, 0)  # one cycle at the end
    return g
tf=mktree(fnx.MultiGraph,3000); tn=mktree(nx.MultiGraph,3000)
row("MG find_cycle (sparse tree+1)", lambda:fnx.find_cycle(tf), lambda:nx.find_cycle(tn))
