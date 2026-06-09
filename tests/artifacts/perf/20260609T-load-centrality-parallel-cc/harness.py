import json, hashlib, time, sys, networkx as nx, franken_networkx as fnx
def mintime(fn, reps=5):
    best=float('inf'); out=None
    for _ in range(reps):
        t=time.perf_counter(); out=fn(); dt=time.perf_counter()-t
        best=min(best,dt)
    return best,out
def sha(d):
    items=sorted((repr(k),repr(v)) for k,v in d.items())
    h=hashlib.sha256()
    for k,v in items: h.update(k.encode());h.update(b'\x00');h.update(v.encode());h.update(b'\x01')
    return h.hexdigest()
def main():
    label=sys.argv[1] if len(sys.argv)>1 else 'run'
    res={}
    for (n,m) in [(1500,4),(2500,4)]:
        g=fnx.barabasi_albert_graph(n,m,seed=42)
        t,s=mintime(lambda: fnx.load_centrality(g),reps=5)
        # multi-shortest-path heavy: grid graph
        gx=nx.gnp_random_graph(1000,0.012,seed=7,directed=True)
        gd=fnx.DiGraph(); gd.add_nodes_from(gx.nodes()); gd.add_edges_from(gx.edges())
        td,sd=mintime(lambda: fnx.load_centrality(gd),reps=3)
        res[f'n{n}']={'n':n,'ms':t*1e3,'sha':sha(s),'dir_ms':td*1e3,'dir_sha':sha(sd)}
        print(f"n={n}: {t*1e3:.1f}ms({res[f'n{n}']['sha'][:10]}) | dir {td*1e3:.1f}ms({res[f'n{n}']['dir_sha'][:10]})")
    json.dump(res, open(f"tests/artifacts/perf/20260609T-load-centrality-parallel-cc/{label}.json","w"), indent=2)
main()
