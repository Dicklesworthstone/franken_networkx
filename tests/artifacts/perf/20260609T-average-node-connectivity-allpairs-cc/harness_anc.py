import sys; sys.path.insert(0, "/data/projects/franken_networkx/python")
import time, hashlib, json, networkx as nx, franken_networkx as fnx
def gen(n): f=getattr(nx,n); return getattr(f,'orig_func',f)
ganc=gen("average_node_connectivity")
def to_fnx(G,d):
    g=fnx.DiGraph() if d else fnx.Graph(); g.add_nodes_from(list(G)); g.add_edges_from(list(G.edges())); return g
def corpus():
    out=[("path6",nx.path_graph(6),False),("cycle9",nx.cycle_graph(9),False),
         ("karate",nx.karate_club_graph(),False),("complete7",nx.complete_graph(7),False),
         ("petersen",nx.petersen_graph(),False),("single",nx.empty_graph(1),False),
         ("two",nx.path_graph(2),False),("empty",nx.empty_graph(0),False)]
    for s in range(3): out.append((f"ws50_{s}",nx.connected_watts_strogatz_graph(50,6,0.3,seed=s),False))
    for s in range(2): out.append((f"dig30_{s}",nx.gnp_random_graph(30,0.2,seed=s,directed=True),True))
    out.append(("disconnected", nx.Graph([(0,1),(2,3),(4,5)]), False))
    return out
def golden():
    rounded=[]; allexact=True
    for name,G,d in corpus():
        fg=to_fnx(G,d)
        a=fnx.average_node_connectivity(fg); b=ganc(G)
        ex = (a==b)
        if not ex: allexact=False; print(f"  MISMATCH {name}: fnx={a} nx={b}")
        rounded.append((name, a if isinstance(a,int) else round(a,12)))
    sha=hashlib.sha256(json.dumps(rounded,sort_keys=True).encode()).hexdigest()
    return allexact, sha
def measure(fn,runs=4,warm=1):
    for _ in range(warm): fn()
    ts=[]
    for _ in range(runs):
        s=time.perf_counter(); fn(); ts.append((time.perf_counter()-s)*1000)
    ts.sort(); return ts[len(ts)//2]
if __name__=="__main__":
    print("fnx file:", fnx.__file__)
    exact, sha = golden()
    G=nx.connected_watts_strogatz_graph(120,6,0.3,seed=7); fg=to_fnx(G,False)
    tn=measure(lambda: fnx.average_node_connectivity(fg)); tx=measure(lambda: ganc(G))
    print(json.dumps({"golden":{"byte_exact":exact,"corpus_sha256":sha},
      "bench_ws120_ms":{"new":round(tn),"genuine_nx":round(tx),"faster_than_nx":round(tx/tn,2)}}, indent=2))
