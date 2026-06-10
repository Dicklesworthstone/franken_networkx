import time, warnings, sys, os; warnings.filterwarnings("ignore")
os.environ["NETWORKX_AUTOMATIC_BACKENDS"]=""
import networkx as nx, franken_networkx as fnx
import franken_networkx.bipartite as fbp
import networkx.algorithms.bipartite as nxbp
try: nx.config.backend_priority=[]
except Exception: pass
def inter(a,b,n=5):
    fa=[]; fb=[]
    for _ in range(n):
        t0=time.perf_counter(); a(); fa.append(time.perf_counter()-t0)
        t0=time.perf_counter(); b(); fb.append(time.perf_counter()-t0)
    return min(fb)*1000, min(fa)*1000
tag=sys.argv[1]
for (a,b,p) in ((150,120,0.05),(250,200,0.04),(400,300,0.03)):
    bn=nx.bipartite.random_graph(a,b,p,seed=3)
    bf=fnx.Graph(); bf.graph.update(bn.graph); bf.add_nodes_from(bn.nodes(data=True)); bf.add_edges_from(bn.edges())
    top=[n for n,d in bn.nodes(data=True) if d['bipartite']==0]
    tf,tn=inter(lambda: nxbp.projected_graph(bn,top), lambda: fbp.projected_graph(bf,top))
    print(f"[{tag}] proj {a}x{b}: fnx={tf:.2f}ms nx={tn:.2f}ms ratio={tf/tn:.2f}x (edges={fbp.projected_graph(bf,top).number_of_edges()})")
