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
bn=nx.bipartite.random_graph(200,160,0.04,seed=3)
bf=fnx.Graph(); bf.graph.update(bn.graph); bf.add_nodes_from(bn.nodes(data=True)); bf.add_edges_from(bn.edges())
top=[n for n,d in bn.nodes(data=True) if d['bipartite']==0]
for name,ff,nf in [("weighted",lambda:fbp.weighted_projected_graph(bf,top),lambda:nxbp.weighted_projected_graph(bn,top)),
                   ("overlap",lambda:fbp.overlap_weighted_projected_graph(bf,top),lambda:nxbp.overlap_weighted_projected_graph(bn,top)),
                   ("generic",lambda:fbp.generic_weighted_projected_graph(bf,top),lambda:nxbp.generic_weighted_projected_graph(bn,top)),
                   ("collab",lambda:fbp.collaboration_weighted_projected_graph(bf,top),lambda:nxbp.collaboration_weighted_projected_graph(bn,top))]:
    tf,tn=inter(nf,ff)
    print(f"[{tag}] {name:9s}: fnx={tf:7.2f}ms nx={tn:7.2f}ms ratio={tf/tn:.2f}x")
