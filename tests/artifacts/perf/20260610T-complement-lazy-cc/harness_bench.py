import time, warnings, sys, os; warnings.filterwarnings("ignore")
os.environ["NETWORKX_AUTOMATIC_BACKENDS"]=""
import networkx as nx, franken_networkx as fnx
try: nx.config.backend_priority=[]
except Exception: pass
def inter(a,b,n=5):
    fa=[]; fb=[]
    for _ in range(n):
        t0=time.perf_counter(); a(); fa.append(time.perf_counter()-t0)
        t0=time.perf_counter(); b(); fb.append(time.perf_counter()-t0)
    return min(fb)*1000, min(fa)*1000
tag=sys.argv[1]
for nn in (1000,1500,2000):
    gf=fnx.gnp_random_graph(nn,0.02,seed=3); gn=nx.gnp_random_graph(nn,0.02,seed=3)
    tf,tn=inter(lambda: nx.complement(gn), lambda: fnx.complement(gf))
    print(f"[{tag}] n={nn}: fnx={tf:.1f}ms nx={tn:.1f}ms ratio={tf/tn:.2f}x")
