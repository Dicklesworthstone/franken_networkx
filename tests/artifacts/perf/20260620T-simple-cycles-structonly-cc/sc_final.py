import time, random, itertools, networkx as nx, franken_networkx as fnx
# parity: fnx.simple_cycles vs nx.simple_cycles directly
from collections import Counter
fails=Counter(); total=Counter()
for seed in range(1500):
    rnd=random.Random(seed); n=rnd.randrange(1,16)
    for cf,cn in [(fnx.DiGraph,nx.DiGraph),(fnx.Graph,nx.Graph),(fnx.MultiDiGraph,nx.MultiDiGraph),(fnx.MultiGraph,nx.MultiGraph)]:
        gf=cf(); gn=cn()
        for i in range(n): gf.add_node(i); gn.add_node(i)
        for _ in range(rnd.randrange(0,26)):
            u,v=rnd.randrange(n),rnd.randrange(n); gf.add_edge(u,v); gn.add_edge(u,v)
        lb=rnd.choice([None,2,4])
        t=cf.__name__; total[t]+=1
        if list(fnx.simple_cycles(gf,length_bound=lb))!=list(nx.simple_cycles(gn,length_bound=lb)): 
            fails[t]+=1
for t in total: print(f"{t:14s}: {fails[t]}/{total[t]} fail")
def best(fn,r=12,w=5):
    for _ in range(w): fn()
    return min((lambda:(t0:=time.perf_counter(),fn(),time.perf_counter()-t0)[2])() for _ in range(r))
def mk(cls,n,m,seed=2):
    g=cls();rnd=random.Random(seed)
    for _ in range(m):
        u,v=rnd.randrange(n),rnd.randrange(n)
        if u!=v: g.add_edge(u,v)
    return g
print("--- perf ---")
for n,m,k in [(1500,7000,50),(1500,7000,200),(500,2000,100)]:
    gf=mk(fnx.DiGraph,n,m);gn=mk(nx.DiGraph,n,m)
    bf=best(lambda:list(itertools.islice(fnx.simple_cycles(gf),k)))
    bn=best(lambda:list(itertools.islice(nx.simple_cycles(gn),k)))
    print(f"DiGraph k={k}: fnx {bf*1000:.2f}ms nx {bn*1000:.2f}ms {bn/bf:.2f}x")
