import time, hashlib, json, sys
import networkx as nx
import franken_networkx as fnx

def build(Gn):
    Gf = fnx.DiGraph() if Gn.is_directed() else fnx.Graph()
    Gf.add_nodes_from(list(Gn.nodes())); Gf.add_edges_from(list(Gn.edges()))
    return Gf

# ---- correctness: golden over many (s,t) pairs across diverse directed graphs ----
def corpus():
    gs = []
    gs.append(nx.gnp_random_graph(300, 0.004, seed=1, directed=True))
    gs.append(nx.gnp_random_graph(300, 0.02, seed=2, directed=True))
    gs.append(nx.gn_graph(300, seed=3))                      # DAG (tree-ish)
    gs.append(nx.scale_free_graph(300, seed=4))              # MultiDiGraph -> DiGraph
    gs.append(nx.cycle_graph(200, create_using=nx.DiGraph))  # directed cycle
    gs.append(nx.path_graph(200, create_using=nx.DiGraph))   # directed path
    gs.append(nx.complete_graph(40, create_using=nx.DiGraph))
    # disconnected: two separate components
    g = nx.DiGraph(); g.add_edges_from([(i,i+1) for i in range(50)]); g.add_edges_from([(100+i,101+i) for i in range(50)]); gs.append(g)
    out=[]
    for g in gs:
        out.append(nx.DiGraph(g))  # collapse multi to simple DiGraph, keep direction
    return out

def golden():
    recs=[]
    for gi, Gn in enumerate(corpus()):
        Gf = build(Gn)
        nodes = list(Gn.nodes())
        # sample pairs deterministically
        pairs=[]
        m=len(nodes)
        for a in range(0, m, max(1,m//20)):
            for b in range(0, m, max(1,m//20)):
                pairs.append((nodes[a], nodes[b]))
        for (s,t) in pairs:
            rn = nx.has_path(Gn, s, t)
            rf = fnx.has_path(Gf, s, t)
            if rn != rf:
                print(f"MISMATCH g{gi} s={s} t={t} nx={rn} fnx={rf}")
                return None
            recs.append(f"{gi}|{s}|{t}|{int(rf)}")
    blob="\n".join(recs)
    return hashlib.sha256(blob.encode()).hexdigest(), len(recs)

def bench():
    N=2000
    D=nx.gnp_random_graph(N,0.004,seed=11,directed=True); Df=build(D)
    # far pair + reachable + unreachable scenarios
    scen=[(0,1500),(0,1999),(123,456)]
    res={}
    for (s,t) in scen:
        def b(fn,g):
            for _ in range(3): fn(g,s,t)
            ts=[]
            for _ in range(2000):
                x=time.perf_counter(); fn(g,s,t); ts.append(time.perf_counter()-x)
            return min(ts)
        tn=b(nx.has_path,D); tf=b(fnx.has_path,Df)
        res[f"{s}->{t}"]={"nx_ms":tn*1000,"fnx_ms":tf*1000,"ratio":tf/tn}
    return res

if __name__=="__main__":
    g=golden()
    if g is None: sys.exit(1)
    sha,nrec=g
    print(f"GOLDEN_SHA={sha} pairs={nrec}")
    print(json.dumps(bench(), indent=2))
