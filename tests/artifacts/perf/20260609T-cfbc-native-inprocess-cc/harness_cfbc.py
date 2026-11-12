import time, sys, hashlib, json
import numpy as np
import networkx as nx
import franken_networkx as fnx

genuine = getattr(nx.current_flow_betweenness_centrality, "orig_func",
                  nx.current_flow_betweenness_centrality)

def to_fnx(G):
    fg = fnx.Graph(); fg.add_nodes_from(list(G)); fg.add_edges_from(list(G.edges(data=True))); return fg

def corpus():
    out=[]
    out.append(("path6", nx.path_graph(6)))
    out.append(("cycle9", nx.cycle_graph(9)))
    out.append(("complete7", nx.complete_graph(7)))
    out.append(("karate", nx.karate_club_graph()))
    out.append(("petersen", nx.petersen_graph()))
    out.append(("wheel12", nx.wheel_graph(12)))
    out.append(("grid3x4", nx.convert_node_labels_to_integers(nx.grid_2d_graph(3,4))))
    for s in range(6):
        out.append((f"gnp30_{s}", nx.gnp_random_graph(30, 0.2, seed=s)))
    for s in range(3):
        out.append((f"ws80_{s}", nx.connected_watts_strogatz_graph(80, 4, 0.3, seed=s)))
    # weighted
    Gw = nx.gnp_random_graph(25, 0.25, seed=3)
    for i,(u,v) in enumerate(Gw.edges()):
        Gw[u][v]["weight"] = 1.0 + (i % 5)
    out.append(("weighted25", Gw))
    return out

def golden():
    maxrel=0.0; rounded=[]
    for name,G in corpus():
        if not nx.is_connected(G):
            G = G.subgraph(max(nx.connected_components(G), key=len)).copy()
            G = nx.convert_node_labels_to_integers(G)
        fg = to_fnx(G)
        w = "weight" if name.startswith("weighted") else None
        fv = fnx.current_flow_betweenness_centrality(fg, weight=w)
        nv = genuine(G, weight=w)
        assert set(fv)==set(nv), f"{name}: key mismatch"
        for k in nv:
            denom = abs(nv[k]) if abs(nv[k])>1e-12 else 1.0
            maxrel = max(maxrel, abs(fv[k]-nv[k])/denom)
            assert isinstance(fv[k], float) and not isinstance(fv[k], np.floating), f"{name}:{k} np leak {type(fv[k])}"
        rounded.append((name, [round(fv[k],10) for k in sorted(fv)]))
    sha = hashlib.sha256(json.dumps(rounded, sort_keys=True).encode()).hexdigest()
    return maxrel, sha

def bench(runs=7):
    G = nx.connected_watts_strogatz_graph(220, 6, 0.3, seed=11)
    fg = to_fnx(G)
    def wm(fn):
        for _ in range(2): fn()
        return min((lambda: (lambda s: ((fn()), (time.perf_counter()-s)*1000)[1])(time.perf_counter()))() for _ in range(runs))
    t_new = wm(lambda: fnx.current_flow_betweenness_centrality(fg))
    t_nx  = wm(lambda: genuine(G))
    return t_new, t_nx

if __name__=="__main__":
    maxrel, sha = golden()
    t_new, t_nx = bench()
    print(json.dumps({
        "golden": {"max_rel_err_vs_nx": maxrel, "corpus_sha256": sha, "within_tol_1e-6": maxrel<1e-6},
        "bench_ws220_ms_warm_min": {"new_inprocess": round(t_new,3), "genuine_nx": round(t_nx,3),
                                     "speedup_vs_nx": round(t_nx/t_new,3)}
    }, indent=2))
