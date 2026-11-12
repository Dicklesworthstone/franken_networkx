"""br-r37-c1-mgisol (CopperCliff): MultiGraph/MultiDiGraph load_centrality via
simple-projection + native kernel (parallel edges don't affect node-path load).
"""
import time, warnings, random
warnings.filterwarnings("ignore")
import networkx as nx, franken_networkx as fnx

def t(fn, k=6):
    b=1e9
    for _ in range(k):
        s=time.perf_counter(); r=fn(); b=min(b,time.perf_counter()-s)
    return b*1e3, r

print("=== HEAD-TO-HEAD vs NetworkX (min of 6) ===")
for C_n, C_f, name in [(nx.MultiGraph, fnx.MultiGraph, "MultiGraph"),
                        (nx.MultiDiGraph, fnx.MultiDiGraph, "MultiDiGraph")]:
    random.seed(1)
    es=[(random.randrange(200),random.randrange(200)) for _ in range(1000)]; es+=es[:250]
    Gn=C_n(); Gn.add_nodes_from(range(200)); Gn.add_edges_from(es)
    Gf=C_f(); Gf.add_nodes_from(range(200)); Gf.add_edges_from(es)
    tn,_=t(lambda: nx.load_centrality(Gn)); tf,_=t(lambda: fnx.load_centrality(Gf))
    print(f"  {name:13s} load_centrality  nx {tn:7.2f}ms fnx {tf:7.2f}ms  {tn/tf:6.2f}x")

print("\n=== PARITY: byte-exact vs nx over random multigraphs (parallels/self-loops/isolates) ===")
mism=0; total=0; maxd=0.0
for seed in range(300):
    random.seed(seed); n=random.randrange(2,28); m=random.randrange(0,n*3)
    es=[(random.randrange(n),random.randrange(n)) for _ in range(m)]; es+=es[:m//4]
    for C_n,C_f in [(nx.MultiGraph,fnx.MultiGraph),(nx.MultiDiGraph,fnx.MultiDiGraph)]:
        Gn=C_n(); Gn.add_nodes_from(range(n)); Gn.add_edges_from(es)
        Gf=C_f(); Gf.add_nodes_from(range(n)); Gf.add_edges_from(es)
        rn=nx.load_centrality(Gn); rf=fnx.load_centrality(Gf); total+=1
        if set(rn)!=set(rf): mism+=1; print("KEY",seed); continue
        d=max((abs(rn[k]-rf[k]) for k in rn), default=0.0); maxd=max(maxd,d)
        if d>1e-9: mism+=1; print(f"VAL seed={seed} d={d}")
print(f"parity: {mism} mismatches over {total} graphs, maxdiff={maxd:.2e}")
