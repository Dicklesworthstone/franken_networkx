import time, sys, hashlib, json, math
import networkx as nx
import franken_networkx as fnx

genuine = getattr(nx.communicability_betweenness_centrality, "orig_func",
                  nx.communicability_betweenness_centrality)

def to_fnx(G):
    fg = fnx.Graph(); fg.add_nodes_from(list(G)); fg.add_edges_from(list(G.edges())); return fg

def corpus():
    out=[]
    out.append(("path7", nx.path_graph(7)))
    out.append(("cycle10", nx.cycle_graph(10)))
    out.append(("complete8", nx.complete_graph(8)))
    out.append(("karate", nx.karate_club_graph()))
    out.append(("petersen", nx.petersen_graph()))
    out.append(("wheel14", nx.wheel_graph(14)))
    out.append(("grid4x5", nx.convert_node_labels_to_integers(nx.grid_2d_graph(4,5))))
    out.append(("dodecahedral", nx.dodecahedral_graph()))
    for s in range(6):
        G = nx.gnp_random_graph(35, 0.18, seed=s)
        if nx.is_connected(G): out.append((f"gnp35_{s}", G))
    for s in range(3):
        out.append((f"ws90_{s}", nx.connected_watts_strogatz_graph(90, 6, 0.3, seed=s)))
    # denser graph: where the old naive Taylor was numerically off
    Gd = nx.gnp_random_graph(60, 0.5, seed=1)
    if nx.is_connected(Gd): out.append(("gnp60_dense", Gd))
    return out

def golden():
    maxrel=0.0; rounded=[]
    for name,G in corpus():
        fv = fnx.communicability_betweenness_centrality(to_fnx(G))
        nv = genuine(G)
        assert set(fv)==set(nv), f"{name}: key mismatch"
        for k in nv:
            a,b = fv[k], nv[k]
            denom = abs(b) if abs(b)>1e-9 else 1.0
            maxrel = max(maxrel, abs(a-b)/denom)
            assert isinstance(a,float) and not isinstance(a, __import__('numpy').floating), f"{name}:{k} np leak"
        rounded.append((name, [round(fv[k],9) for k in sorted(fv)]))
    sha = hashlib.sha256(json.dumps(rounded, sort_keys=True).encode()).hexdigest()
    return maxrel, sha

def bench(runs=7):
    G = nx.connected_watts_strogatz_graph(220, 6, 0.3, seed=11)
    fg = to_fnx(G)
    for _ in range(2): fnx.communicability_betweenness_centrality(fg)
    best=1e18
    for _ in range(runs):
        s=time.perf_counter(); fnx.communicability_betweenness_centrality(fg); best=min(best,(time.perf_counter()-s)*1000)
    # also time nx once (it's ~10x slower so 2 reps)
    bnx=1e18
    for _ in range(2):
        s=time.perf_counter(); genuine(G); bnx=min(bnx,(time.perf_counter()-s)*1000)
    return best, bnx

if __name__=="__main__":
    maxrel, sha = golden()
    t_new, t_nx = bench()
    print(json.dumps({
        "package": fnx._fnx.__file__,
        "golden": {"max_rel_err_vs_nx": maxrel, "corpus_sha256": sha, "within_tol_1e-6": maxrel<1e-6},
        "bench_ws220_ms_warm_min": {"fnx_new": round(t_new,2), "genuine_nx": round(t_nx,2),
                                    "fnx_faster_than_nx": round(t_nx/t_new,2)}
    }, indent=2))
