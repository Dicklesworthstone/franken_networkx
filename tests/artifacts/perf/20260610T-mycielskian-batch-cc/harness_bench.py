import time, warnings, sys, os; warnings.filterwarnings("ignore")
os.environ["NETWORKX_AUTOMATIC_BACKENDS"]=""
import networkx as nx, franken_networkx as fnx
try: nx.config.backend_priority=[]
except Exception: pass
def inter(a,b,n=6):
    fa=[]; fb=[]
    for _ in range(n):
        t0=time.perf_counter(); a(); fa.append(time.perf_counter()-t0)
        t0=time.perf_counter(); b(); fb.append(time.perf_counter()-t0)
    return min(fb)*1000, min(fa)*1000
tag=sys.argv[1]
for n,p in ((200,0.1),(400,0.06),(150,0.2)):
    gn=nx.gnp_random_graph(n,p,seed=3); gf=fnx.Graph(); gf.add_nodes_from(gn.nodes()); gf.add_edges_from(gn.edges())
    tf,tn=inter(lambda: nx.mycielskian(gn), lambda: fnx.mycielskian(gf))
    print(f"[{tag}] mycielskian n={n} p={p}: fnx={tf:.2f}ms nx={tn:.2f}ms ratio={tf/tn:.2f}x")
