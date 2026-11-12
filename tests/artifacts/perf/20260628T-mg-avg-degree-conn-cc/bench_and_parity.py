import time, warnings, random
warnings.filterwarnings("ignore")
import networkx as nx, franken_networkx as fnx
def t(fn,k=6):
    b=1e9
    for _ in range(k): s=time.perf_counter(); fn(); b=min(b,time.perf_counter()-s)
    return b*1e3
random.seed(13); es=[(random.randrange(200),random.randrange(200)) for _ in range(900)]; es+=es[:200]
Gn=nx.MultiGraph(); Gn.add_nodes_from(range(200)); Gn.add_edges_from(es)
Gf=fnx.MultiGraph(); Gf.add_nodes_from(range(200)); Gf.add_edges_from(es)
print(f"average_degree_connectivity(MG) n=200: nx {t(lambda:nx.average_degree_connectivity(Gn)):.2f}ms fnx {t(lambda:fnx.average_degree_connectivity(Gf)):.2f}ms")
mism=0;total=0;maxd=0.0
for seed in range(400):
    random.seed(seed); n=random.randrange(1,30); m=random.randrange(0,n*3)
    es=[(random.randrange(n),random.randrange(n)) for _ in range(m)]; es+=es[:m//4]
    for Cn,Cf in [(nx.MultiGraph,fnx.MultiGraph),(nx.Graph,fnx.Graph),(nx.MultiDiGraph,fnx.MultiDiGraph)]:
        Gn=Cn(); Gn.add_nodes_from(range(n)); Gn.add_edges_from(es)
        Gf=Cf(); Gf.add_nodes_from(range(n)); Gf.add_edges_from(es)
        rn=nx.average_degree_connectivity(Gn); rf=fnx.average_degree_connectivity(Gf); total+=1
        if set(rn)!=set(rf): mism+=1; continue
        maxd=max(maxd, max((abs(rn[k]-rf[k]) for k in rn), default=0.0))
print(f"parity: {mism}/{total} maxdiff={maxd:.2e}")
