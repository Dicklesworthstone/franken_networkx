import json, hashlib, time, sys, networkx as nx, franken_networkx as fnx

def mintime(fn, reps=5):
    best=float('inf'); out=None
    for _ in range(reps):
        t=time.perf_counter(); out=fn(); dt=time.perf_counter()-t
        best=min(best,dt)
    return best,out

def sha_edge(d):
    # d: dict keyed by (u,v) edge tuple -> float
    items=sorted((repr(tuple(sorted(map(repr,k)))), repr(v)) for k,v in d.items())
    h=hashlib.sha256()
    for k,v in items:
        h.update(k.encode()); h.update(b'\x00'); h.update(v.encode()); h.update(b'\x01')
    return h.hexdigest()

def main():
    label=sys.argv[1] if len(sys.argv)>1 else 'run'
    res={}
    for (n,m) in [(1500,4),(2500,4)]:
        g=fnx.barabasi_albert_graph(n,m,seed=42)
        t,scores=mintime(lambda: fnx.edge_betweenness_centrality(g), reps=5)
        # directed variant
        gx=nx.gnp_random_graph(800,0.01,seed=7,directed=True)
        gd=fnx.DiGraph(); gd.add_nodes_from(gx.nodes()); gd.add_edges_from(gx.edges())
        td,sd=mintime(lambda: fnx.edge_betweenness_centrality(gd), reps=3)
        res[f'n{n}_m{m}']={'n':n,'m':m,'time_ms':t*1e3,'sha':sha_edge(scores),
                           'dir_time_ms':td*1e3,'dir_sha':sha_edge(sd)}
        print(f"n={n} m={m}: {t*1e3:.2f}ms sha={res[f'n{n}_m{m}']['sha'][:12]} | dir={td*1e3:.2f}ms dsha={res[f'n{n}_m{m}']['dir_sha'][:12]}")
    json.dump(res, open(f"tests/artifacts/perf/20260609T-edge-betweenness-parallel-csr-cc/{label}.json","w"), indent=2)

main()
