import time, sys, hashlib, json
import numpy as np
import networkx as nx
import franken_networkx as fnx

def gen(name):
    fn=getattr(nx,name); return getattr(fn,"orig_func",fn)
gs = gen("simrank_similarity")

def to_fnx(G, directed=False, weighted=False):
    fg = fnx.DiGraph() if directed else fnx.Graph()
    fg.add_nodes_from(list(G))
    fg.add_edges_from(list(G.edges(data=True)))
    return fg

def corpus():
    out=[]
    out.append(("path8", nx.path_graph(8), False, False))
    out.append(("cycle10", nx.cycle_graph(10), False, False))
    out.append(("karate", nx.karate_club_graph(), False, False))
    out.append(("complete7", nx.complete_graph(7), False, False))
    for s in range(4):
        out.append((f"gnp30_{s}", nx.gnp_random_graph(30,0.2,seed=s), False, False))
    out.append(("digraph40", nx.gnp_random_graph(40,0.2,seed=1,directed=True), True, False))
    out.append(("digraph_scc", nx.scale_free_graph(35, seed=2) if False else nx.gn_graph(30, seed=2), True, False))
    Gw=nx.gnp_random_graph(30,0.25,seed=3)
    import random; rnd=random.Random(7)
    for u,v in Gw.edges(): Gw[u][v]["weight"]=rnd.randint(1,6)
    out.append(("weighted30", Gw, False, True))
    return out

def golden():
    maxrel=0.0; rounded=[]
    for name,G,directed,weighted in corpus():
        fg = to_fnx(G, directed, weighted)
        # source+target (float)
        nodes=list(G); s=nodes[0]; t=nodes[min(5,len(nodes)-1)]
        fv=fnx.simrank_similarity(fg, source=s, target=t)
        nv=gs(G, source=s, target=t)
        assert isinstance(fv,float) and not isinstance(fv,np.floating), f"{name}: np leak"
        denom=abs(nv) if abs(nv)>1e-12 else 1.0
        maxrel=max(maxrel, abs(fv-nv)/denom)
        # full matrix (dict of dicts)
        fm=fnx.simrank_similarity(fg); nm=gs(G)
        assert set(fm)==set(nm), f"{name}: key mismatch"
        for u in nm:
            for v in nm[u]:
                d=abs(nm[u][v]) if abs(nm[u][v])>1e-12 else 1.0
                maxrel=max(maxrel, abs(fm[u][v]-nm[u][v])/d)
        rounded.append((name, round(fv,10)))
    sha=hashlib.sha256(json.dumps(rounded,sort_keys=True).encode()).hexdigest()
    return maxrel, sha

def bench(runs=7):
    G=nx.connected_watts_strogatz_graph(300,8,0.3,seed=11)
    fg=to_fnx(G)
    def wm(fn):
        for _ in range(2): fn()
        return min((lambda s: ((fn()),(time.perf_counter()-s)*1000)[1])(time.perf_counter()) for _ in range(runs))
    t_new=wm(lambda: fnx.simrank_similarity(fg, source=0, target=10))
    t_nx=wm(lambda: gs(G, source=0, target=10))
    return t_new, t_nx

if __name__=="__main__":
    maxrel, sha = golden()
    t_new, t_nx = bench()
    print(json.dumps({
        "golden": {"max_rel_err_vs_nx": maxrel, "corpus_sha256": sha, "byte_exact": maxrel==0.0},
        "bench_ws300_ms_warm_min": {"new_inprocess": round(t_new,2), "genuine_nx": round(t_nx,2),
                                    "faster_than_nx": round(t_nx/t_new,3)}
    }, indent=2))
