import random, time
import networkx as nx, franken_networkx as fnx
def build(seed, sl):
    rng=random.Random(seed); n=rng.randint(4,14)
    base=nx.gnp_random_graph(n,0.3,seed=seed)
    Gn=nx.Graph(); Gf=fnx.Graph(); Gn.add_nodes_from(base.nodes()); Gf.add_nodes_from(base.nodes())
    es=list(base.edges())
    if sl:
        for x in list(base.nodes())[:2]: es.append((x,x))
    for u,v in es:
        w=rng.randint(1,9); Gn.add_edge(u,v,weight=w,t=[u,v]); Gf.add_edge(u,v,weight=w,t=[u,v])
    for x in list(base.nodes())[:3]: Gn.nodes[x]['c']=str(x); Gf.nodes[x]['c']=str(x)
    Gn.graph['g']='x'; Gf.graph['g']='x'
    return Gf,Gn
def sig(G):
    return (list(G.nodes()), [(u,v,tuple(sorted((k,str(val)) for k,val in d.items()))) for u,v,d in G.edges(data=True)],
            sorted((k,str(v)) for k,v in G.graph.items()),
            [(n,tuple(sorted((k,str(val)) for k,val in d.items()))) for n,d in G.nodes(data=True)])
mism=0; cases=0
for seed in range(500):
    for sl in (0,1):
        Gf,Gn=build(seed,sl)
        Df=Gf.to_directed(); Dn=Gn.to_directed()
        if not Df.is_directed() or not Dn.is_directed(): mism+=1; print('not directed',seed)
        if sig(Df)!=sig(Dn): 
            mism+=1
            if mism<=4:
                sf,sn=sig(Df),sig(Dn)
                for i,nm in enumerate(['nodes','edges','graph','nodeattrs']):
                    if sf[i]!=sn[i]: print(f'{nm} seed{seed} nx={sn[i][:4]} fx={sf[i][:4]}')
        # deepcopy independence: mutate result edge attr list, original unchanged
        edges_f=list(Gf.edges())
        if not edges_f: cases+=1; continue
        eu,ev=edges_f[0]
        d=Df[eu][ev]['t']; d.append('Z')
        if 'Z' in Gf[eu][ev]['t']: mism+=1; print('NOT deepcopied (shared list)',seed)
        cases+=1
print(f"to_directed parity: cases={cases} mismatches={mism}")
# bench
def wm(fn,r=6):
    ts=[]
    for _ in range(r): t=time.perf_counter(); fn(); ts.append(time.perf_counter()-t)
    return min(ts)
Gf=fnx.connected_watts_strogatz_graph(8000,10,0.15,seed=7); Gn=nx.connected_watts_strogatz_graph(8000,10,0.15,seed=7)
tf=wm(lambda:Gf.to_directed()); tn=wm(lambda:Gn.to_directed())
print(f"to_directed n=8000: fnx {tf*1000:.1f}ms nx {tn*1000:.1f}ms ratio {tf/tn:.2f}x")
