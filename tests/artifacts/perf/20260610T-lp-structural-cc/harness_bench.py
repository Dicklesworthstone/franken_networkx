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
for nn,p in ((800,0.03),(1200,0.02),(1500,0.02)):
    gf=fnx.gnp_random_graph(nn,p,seed=3); gn=nx.gnp_random_graph(nn,p,seed=3)
    tf,tn=inter(lambda: list(nx.community.label_propagation_communities(gn)), lambda: list(fnx.community.label_propagation_communities(gf)))
    print(f"[{tag}] n={nn}: fnx={tf:.2f}ms nx={tn:.2f}ms ratio={tf/tn:.2f}x")
