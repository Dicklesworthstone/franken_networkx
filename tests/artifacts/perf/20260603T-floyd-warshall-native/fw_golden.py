import franken_networkx as fnx, networkx as nx, numpy as np, random, hashlib
def build(M, seed, n, e, w='rand', sl=True, neg=False):
    g=M(); r=random.Random(seed); g.add_nodes_from(range(n))
    tries=0
    while g.number_of_edges()<e and tries<e*50:
        tries+=1
        u,v=r.randint(0,n-1),r.randint(0,n-1)
        if not sl and u==v: continue
        if w=='none': g.add_edge(u,v)
        elif w=='neg': g.add_edge(u,v,weight=round(r.random()*2-0.5,3))
        elif w=='zero': g.add_edge(u,v,weight=0.0 if r.random()<0.3 else round(r.random()+.1,3))
        else: g.add_edge(u,v,weight=round(r.random()+.1,3))
    return g
mism=0
for label,Mf,Mn in [("Graph",fnx.Graph,nx.Graph),("DiGraph",fnx.DiGraph,nx.DiGraph)]:
    for seed in (1,2,3):
        for n,e in [(40,150),(60,80),(30,400)]:
            for w in ('rand','none','zero'):
                for sl in (True,False):
                    gf=build(Mf,seed,n,e,w=w,sl=sl); gn=build(Mn,seed,n,e,w=w,sl=sl)
                    Df=fnx.floyd_warshall_numpy(gf); Dn=nx.floyd_warshall_numpy(gn)
                    if not np.array_equal(Df,Dn):
                        # array_equal treats inf==inf True, nan!=nan; check
                        if not (np.array_equal(np.nan_to_num(Df,posinf=1e18),np.nan_to_num(Dn,posinf=1e18))):
                            mism+=1; print(f"  MISMATCH {label} s={seed} n={n} e={e} w={w} sl={sl} maxdiff={np.max(np.abs(np.nan_to_num(Df-Dn)))}")
# negative weights (DiGraph, no neg cycle risk on sparse small)
gf=build(fnx.DiGraph,5,20,40,w='neg',sl=False); gn=build(nx.DiGraph,5,20,40,w='neg',sl=False)
if not np.array_equal(fnx.floyd_warshall_numpy(gf), nx.floyd_warshall_numpy(gn)): mism+=1; print("  NEG mismatch")
# golden hash on a fixed case
gf=build(fnx.Graph,7,50,300); D=fnx.floyd_warshall_numpy(gf)
print(f"mismatches={mism}")
print(f"FW_GOLDEN {hashlib.sha256(np.ascontiguousarray(D).tobytes()).hexdigest()}")
