import json, time, sys, math, networkx as nx, franken_networkx as fnx
def mintime(fn, reps=5):
    best=float('inf'); out=None
    for _ in range(reps):
        t=time.perf_counter(); out=fn(); dt=time.perf_counter()-t
        best=min(best,dt)
    return best,out
def main():
    label=sys.argv[1] if len(sys.argv)>1 else 'run'
    res={}
    for (n,m) in [(2000,4),(3500,4)]:
        g=fnx.barabasi_albert_graph(n,m,seed=42)
        t,v=mintime(lambda: fnx.average_shortest_path_length(g),reps=5)
        # directed strongly-connected-ish: cycle + random
        gx=nx.gnp_random_graph(900,0.02,seed=7,directed=True)
        # ensure strongly connected by adding a hamiltonian-ish cycle
        nodes=list(gx.nodes())
        for i in range(len(nodes)): gx.add_edge(nodes[i], nodes[(i+1)%len(nodes)])
        gd=fnx.DiGraph(); gd.add_nodes_from(gx.nodes()); gd.add_edges_from(gx.edges())
        td,vd=mintime(lambda: fnx.average_shortest_path_length(gd),reps=3)
        res[f'n{n}']={'n':n,'ms':t*1e3,'val':repr(v),'dir_ms':td*1e3,'dir_val':repr(vd)}
        print(f"n={n}: {t*1e3:.1f}ms val={v!r} | dir {td*1e3:.1f}ms val={vd!r}")
    json.dump(res, open(f"tests/artifacts/perf/20260609T-aspl-parallel-cc/{label}.json","w"), indent=2)
main()
