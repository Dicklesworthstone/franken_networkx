import franken_networkx as fnx, networkx as nx, random, time
def build(n, seed, deg=4):
    rng=random.Random(seed); es=set()
    while len(es) < n*deg:
        u=rng.randrange(n); v=rng.randrange(n)
        if u!=v: es.add((min(u,v),max(u,v)))
    Gf=fnx.Graph(); Gf.add_nodes_from(range(n)); Gn=nx.Graph(); Gn.add_nodes_from(range(n))
    for u,v in es:
        w=rng.randint(1,20); Gf.add_edge(u,v,weight=w); Gn.add_edge(u,v,weight=w)
    return Gf,Gn
def best(fn,reps=40):
    b=1e9
    for _ in range(reps):
        a=time.perf_counter(); fn(); b=min(b,time.perf_counter()-a)
    return b*1e3
print(f"{'n':>6} {'native':>9} {'old_local':>10} {'nx':>8} {'vs_nx':>7} {'self_speedup':>13}")
for n in [500,1000,2000,3000,5000]:
    Gf,Gn=build(n,7); s,t=0,n-1
    fnx.bidirectional_dijkstra(Gf,s,t,weight='weight'); nx.bidirectional_dijkstra(Gn,s,t,weight='weight')
    tn=best(lambda: fnx.bidirectional_dijkstra(Gf,s,t,weight='weight'))
    tl=best(lambda: fnx._bidirectional_dijkstra_local(Gf,s,t,'weight'))
    tx=best(lambda: nx.bidirectional_dijkstra(Gn,s,t,weight='weight'))
    print(f"{n:>6} {tn:>8.3f}m {tl:>9.3f}m {tx:>7.3f}m {tx/tn:>6.2f}x {tl/tn:>12.2f}x")
