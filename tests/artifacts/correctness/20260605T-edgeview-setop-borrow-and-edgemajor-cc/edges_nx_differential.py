import os,time,hashlib,random
for v in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']: os.environ[v]='2'
import networkx as nx, franken_networkx as fnx
def build(mod,kind,n,p,seed,sl):
    d=kind=='d'; cls=(mod.DiGraph if d else mod.Graph)
    base=nx.gnp_random_graph(n,p,seed=seed,directed=d)
    G=cls(); G.add_nodes_from(base.nodes())
    rng=random.Random(seed); es=list(base.edges())
    if sl:
        for x in list(base.nodes())[:2]: es.append((x,x))
    for u,v in es:
        if rng.random()<0.6: G.add_edge(u,v,weight=rng.randint(1,9),t='x%d'%u)
        else: G.add_edge(u,v)
    return G
mism=0; cases=0
for kind in ('u','d'):
    for c in range(40):
        Gn=build(nx,kind,6+c%14,0.25,500+c,c%3==0); Gf=build(fnx,kind,6+c%14,0.25,500+c,c%3==0)
        # data=True full
        if list(Gf.edges(data=True))!=list(Gn.edges(data=True)): mism+=1; print('ED diff',kind,c) if mism<=3 else None
        # data=False
        if list(Gf.edges())!=list(Gn.edges()): mism+=1
        # identity d is G[u][v]
        idf=[d is Gf[u][v] for u,v,d in Gf.edges(data=True)]; idn=[d is Gn[u][v] for u,v,d in Gn.edges(data=True)]
        if idf!=idn: mism+=1; print('IDENT diff',kind,c) if mism<=3 else None
        # nbunch data=True
        nb=list(Gn.nodes())[:3]
        if list(Gf.edges(nb,data=True))!=list(Gn.edges(nb,data=True)): mism+=1; print('NB-ED diff',kind,c) if mism<=3 else None
        # data='weight'
        if list(Gf.edges(data='weight'))!=list(Gn.edges(data='weight')): mism+=1
        cases+=1
print(f"vs-nx cases={cases} mismatches={mism}")
# bench
def wm(fn,r=12):
    ts=[]
    for _ in range(r):
        t=time.perf_counter(); fn(); ts.append(time.perf_counter()-t)
    return min(ts)
for n in (1500,4000):
    Gf=fnx.connected_watts_strogatz_graph(n,8,0.2,seed=3); Gn=nx.connected_watts_strogatz_graph(n,8,0.2,seed=3)
    tf=wm(lambda:list(Gf.edges(data=True))); tn=wm(lambda:list(Gn.edges(data=True)))
    print(f"edges(data=True) n={n}: fnx {tf*1000:.2f} nx {tn*1000:.2f} ratio {tf/tn:.2f}x")
