import time, warnings, sys, os; warnings.filterwarnings("ignore")
os.environ["NETWORKX_AUTOMATIC_BACKENDS"]=""
import networkx as nx, franken_networkx as fnx
try: nx.config.backend_priority=[]
except Exception: pass
def inter(a,b,n=4):
    fa=[]; fb=[]
    for _ in range(n):
        t0=time.perf_counter(); a(); fa.append(time.perf_counter()-t0)
        t0=time.perf_counter(); b(); fb.append(time.perf_counter()-t0)
    return min(fb)*1000, min(fa)*1000
tag=sys.argv[1]
for nn,p in ((1000,0.1),(1500,0.1),(1500,0.3),(2000,0.05)):
    tf,tn=inter(lambda: nx.gnp_random_graph(nn,p,seed=3,directed=True), lambda: fnx.gnp_random_graph(nn,p,seed=3,directed=True))
    print(f"[{tag}] gnp_di n={nn} p={p}: fnx={tf:.1f}ms nx={tn:.1f}ms ratio={tf/tn:.2f}x")
