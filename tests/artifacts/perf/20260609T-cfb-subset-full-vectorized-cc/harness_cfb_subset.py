import time, sys, hashlib, json
import numpy as np
import networkx as nx
import franken_networkx as fnx
def gen(n): f=getattr(nx,n); return getattr(f,'orig_func',f)
gnode=gen('current_flow_betweenness_centrality_subset')
gedge=gen('edge_current_flow_betweenness_centrality_subset')

def to_fnx(G):
    fg=fnx.Graph(); fg.add_nodes_from(list(G)); fg.add_edges_from(list(G.edges(data=True))); return fg

def corpus():
    out=[]
    out.append(("path6", nx.path_graph(6)))
    out.append(("cycle9", nx.cycle_graph(9)))
    out.append(("karate", nx.karate_club_graph()))
    out.append(("wheel12", nx.wheel_graph(12)))
    for s in range(3):
        G=nx.gnp_random_graph(40,0.2,seed=s)
        if nx.is_connected(G): out.append((f"gnp40_{s}", G))
    Gw=nx.gnp_random_graph(35,0.25,seed=4)
    import random; rnd=random.Random(1)
    for u,v in Gw.edges(): Gw[u][v]["weight"]=rnd.randint(1,6)
    if nx.is_connected(Gw): out.append(("weighted35", Gw))
    return out

def golden():
    maxrel=0.0; rounded=[]
    for name,G in corpus():
        fg=to_fnx(G); nodes=list(G)
        src=nodes[:max(2,len(nodes)//4)]; tgt=nodes[len(nodes)//2:len(nodes)//2+max(2,len(nodes)//4)]
        w = "weight" if name.startswith("weighted") else None
        for norm in (True, False):
            fn=fnx.current_flow_betweenness_centrality_subset(fg, src, tgt, normalized=norm, weight=w)
            nn=gnode(G, src, tgt, normalized=norm, weight=w)
            for k in nn:
                d=abs(nn[k]) if abs(nn[k])>1e-12 else 1.0
                maxrel=max(maxrel, abs(fn[k]-nn[k])/d)
            fe=fnx.edge_current_flow_betweenness_centrality_subset(fg, src, tgt, normalized=norm, weight=w)
            ne=gedge(G, src, tgt, normalized=norm, weight=w)
            assert set(fe)==set(ne), f"{name}: edge key mismatch"
            for k in ne:
                d=abs(ne[k]) if abs(ne[k])>1e-12 else 1.0
                maxrel=max(maxrel, abs(fe[k]-ne[k])/d)
        rounded.append((name, [round(fn[k],9) for k in sorted(fn, key=str)]))
    sha=hashlib.sha256(json.dumps(rounded,sort_keys=True,default=str).encode()).hexdigest()
    return maxrel, sha

def bench(runs=3):
    G=nx.connected_watts_strogatz_graph(300,8,0.3,seed=11); fg=to_fnx(G); sub=list(G)[:40]; subf=list(fg)[:40]
    def wm(fn):
        for _ in range(1): fn()
        return min((lambda s: ((fn()),(time.perf_counter()-s)*1000)[1])(time.perf_counter()) for _ in range(runs))
    tn=wm(lambda: fnx.current_flow_betweenness_centrality_subset(fg, subf, subf))
    tnx=wm(lambda: gnode(G, sub, sub))
    return tn, tnx

if __name__=="__main__":
    maxrel, sha = golden(); tn, tnx = bench()
    print(json.dumps({
        "golden":{"max_rel_err_vs_nx":maxrel,"within_tol_1e-6":maxrel<1e-6,"corpus_sha256":sha},
        "bench_ws300_sub40_ms_warm_min":{"new_inprocess":round(tn,1),"genuine_nx":round(tnx,1),"faster_than_nx":round(tnx/tn,2)}
    }, indent=2))
