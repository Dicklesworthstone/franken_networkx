import time, warnings, sys, os; warnings.filterwarnings("ignore")
os.environ["NETWORKX_AUTOMATIC_BACKENDS"]=""
import networkx as nx, franken_networkx as fnx
try: nx.config.backend_priority=[]
except Exception: pass
def inter(a,b,n=9):
    fa=[]; fb=[]
    for _ in range(n):
        t0=time.perf_counter(); a(); fa.append(time.perf_counter()-t0)
        t0=time.perf_counter(); b(); fb.append(time.perf_counter()-t0)
    return min(fb)*1000, min(fa)*1000
tag=sys.argv[1]
for nn in (800,1500,2500):
    gf=fnx.gnp_random_graph(nn,0.02,seed=3,directed=True); gn=nx.gnp_random_graph(nn,0.02,seed=3,directed=True)
    tf,tn=inter(lambda: nx.overall_reciprocity(gn), lambda: fnx.overall_reciprocity(gf))
    tf2,tn2=inter(lambda: nx.reciprocity(gn,list(gn)), lambda: fnx.reciprocity(gf,list(gf)))
    print(f"[{tag}] n={nn} E={gf.number_of_edges()}: overall fnx={tf:.2f} nx={tn:.2f} ({tf/tn:.2f}x) | per-node fnx={tf2:.2f} nx={tn2:.2f} ({tf2/tn2:.2f}x)")
