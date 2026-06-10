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
for n,p in ((400,0.04),(800,0.025),(1500,0.012)):
    un=nx.gnp_random_graph(n,p,seed=3); uf=fnx.Graph(); uf.add_nodes_from(un.nodes()); uf.add_edges_from(un.edges())
    tf,tn=inter(lambda: nx.greedy_color(un,strategy="smallest_last"), lambda: fnx.greedy_color(uf,strategy="smallest_last"))
    print(f"[{tag}] smallest_last n={n}: fnx={tf:.2f}ms nx={tn:.2f}ms ratio={tf/tn:.2f}x")
