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
    for (n,m) in [(2000,4),(3000,4)]:
        g=fnx.barabasi_albert_graph(n,m,seed=42)
        tc,sc=mintime(lambda: fnx.closeness_centrality(g),reps=5)
        th,sh=mintime(lambda: fnx.harmonic_centrality(g),reps=5)
        # directed
        gx=nx.gnp_random_graph(1200,0.01,seed=7,directed=True)
        gd=fnx.DiGraph(); gd.add_nodes_from(gx.nodes()); gd.add_edges_from(gx.edges())
        tcd,scd=mintime(lambda: fnx.closeness_centrality(gd),reps=3)
        thd,shd=mintime(lambda: fnx.harmonic_centrality(gd),reps=3)
        res[f'n{n}']={'n':n,'clo_ms':tc*1e3,'clo_sha':sha(sc),'har_ms':th*1e3,'har_sha':sha(sh),
                      'clo_dir_ms':tcd*1e3,'clo_dir_sha':sha(scd),'har_dir_ms':thd*1e3,'har_dir_sha':sha(shd)}
        r=res[f'n{n}']
        print(f"n={n}: clo {tc*1e3:.1f}ms({r['clo_sha'][:10]}) har {th*1e3:.1f}ms({r['har_sha'][:10]}) | dir clo {tcd*1e3:.1f}ms har {thd*1e3:.1f}ms")
    json.dump(res, open(f"tests/artifacts/perf/20260609T-closeness-harmonic-parallel-cc/{label}.json","w"), indent=2)
main()
