import hashlib, json, networkx as nx, franken_networkx as fnx
def sig(G):
    e_nodata = [(repr(u),repr(v)) for u,v in G.edges()]
    e_alldata = [(repr(u),repr(v),sorted(d.items())) for u,v,d in G.edges(data=True)]
    e_attr = [(repr(u),repr(v),G.edges[u,v].get('weight') if (u,v) in [(a,b) for a,b in G.edges()] else None) for u,v in G.edges()]
    e_w = [(repr(u),repr(v),w) for u,v,w in G.edges(data='weight')]
    e_wd = [(repr(u),repr(v),w) for u,v,w in G.edges(data='weight', default=-1)]
    return json.dumps([e_nodata,e_alldata,e_w,e_wd])
mism=0; sigs={}
import random
for N,m,seed in [(800,4,5),(200,3,11),(40,2,1)]:
    Gf=fnx.barabasi_albert_graph(N,m,seed=seed); Gn=nx.barabasi_albert_graph(N,m,seed=seed)
    r=random.Random(seed)
    for u,v in list(Gn.edges())[:N//2]:
        w=r.random(); Gn[u][v]['weight']=w; Gf[u][v]['weight']=w
    sf=sig(Gf); sn=sig(Gn)
    sigs[f"N{N}"]=hashlib.sha256(sf.encode()).hexdigest()
    if sf!=sn: mism+=1; print(f"MISMATCH N{N}")
print(f"mismatches(vs nx)={mism} cases={len(sigs)}")
print("EDGES_GOLDEN", hashlib.sha256("|".join(f"{k}={sigs[k]}" for k in sorted(sigs)).encode()).hexdigest())
