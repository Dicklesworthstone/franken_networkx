import time, hashlib, json, sys
import networkx as nx, franken_networkx as fnx

def build(Gn):
    Gf=fnx.DiGraph(); Gf.add_nodes_from(list(Gn.nodes())); Gf.add_edges_from(list(Gn.edges()))
    return Gf

def corpus():
    gs=[]
    gs.append(nx.gnp_random_graph(200,0.02,seed=1,directed=True))
    gs.append(nx.gnp_random_graph(200,0.08,seed=2,directed=True))
    gs.append(nx.gn_graph(200,seed=3))
    g=nx.scale_free_graph(200,seed=4); gs.append(nx.DiGraph(g))  # antiparallel + multi collapse
    gs.append(nx.cycle_graph(100,create_using=nx.DiGraph))
    # bidirectional complete-ish (lots of antiparallel)
    bg=nx.DiGraph()
    import itertools
    for u,v in itertools.permutations(range(25),2): bg.add_edge(u,v)
    gs.append(bg)
    # disconnected + isolated nodes
    dd=nx.DiGraph(); dd.add_edges_from([(i,i+1) for i in range(30)]); dd.add_nodes_from([100,101,102]); gs.append(dd)
    for g in gs:
        g.remove_edges_from(list(nx.selfloop_edges(g)))  # core_number forbids self-loops
    return gs

def golden():
    recs=[]
    for gi,Gn in enumerate(corpus()):
        Gf=build(Gn)
        rn=nx.core_number(Gn); rf=fnx.core_number(Gf)
        if rn!=rf:
            # find first diff
            for k in rn:
                if rn.get(k)!=rf.get(k): print(f"MISMATCH g{gi} node={k} nx={rn.get(k)} fnx={rf.get(k)}"); return None
            print(f"MISMATCH g{gi} keyset/order differs len nx={len(rn)} fnx={len(rf)}"); return None
        # also check key ORDER matches (dict order)
        if list(rn.keys())!=list(rf.keys()):
            print(f"KEYORDER mismatch g{gi}"); return None
        recs.append(f"{gi}|"+"|".join(f"{k}:{rf[k]}" for k in rf))
    return hashlib.sha256("\n".join(recs).encode()).hexdigest()

def bench():
    DG=nx.gnp_random_graph(250,0.02,seed=5,directed=True); Df=build(DG)
    def b(fn,g):
        for _ in range(3): fn(g)
        ts=[]
        for _ in range(200):
            x=time.perf_counter(); fn(g); ts.append(time.perf_counter()-x)
        return min(ts)
    tn=b(nx.core_number,DG); tf=b(fnx.core_number,Df)
    return {"n250_dir":{"nx_ms":tn*1000,"fnx_ms":tf*1000,"ratio":tf/tn}}

if __name__=="__main__":
    sha=golden()
    if sha is None: sys.exit(1)
    print("GOLDEN_SHA="+sha)
    print(json.dumps(bench(),indent=2))
