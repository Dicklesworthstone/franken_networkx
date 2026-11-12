import time, warnings, sys, os; warnings.filterwarnings("ignore")
os.environ["NETWORKX_AUTOMATIC_BACKENDS"]=""
import networkx as nx, franken_networkx as fnx
import networkx.algorithms.approximation as nxa
import franken_networkx.approximation as fa
try: nx.config.backend_priority=[]
except Exception: pass
def inter(a,b,n=9):
    fa_=[]; fb=[]
    for _ in range(n):
        t0=time.perf_counter(); a(); fa_.append(time.perf_counter()-t0)
        t0=time.perf_counter(); b(); fb.append(time.perf_counter()-t0)
    return min(fb)*1000, min(fa_)*1000
tag=sys.argv[1]
for n,p in ((400,0.04),(800,0.02),(1500,0.01)):
    un=nx.gnp_random_graph(n,p,seed=3); uf=fnx.Graph(); uf.add_nodes_from(un.nodes()); uf.add_edges_from(un.edges())
    s,t=0,n//2
    tf,tn=inter(lambda: nxa.local_node_connectivity(un,s,t), lambda: fa.local_node_connectivity(uf,s,t))
    print(f"[{tag}] n={n}: fnx={tf:.3f}ms nx={tn:.3f}ms ratio={tf/tn:.2f}x")
