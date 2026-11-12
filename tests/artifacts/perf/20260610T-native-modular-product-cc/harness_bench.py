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
for (a,b) in ((25,20),(30,25),(40,30)):
    g1=fnx.path_graph(a); gn1=nx.path_graph(a); g2=fnx.cycle_graph(b); gn2=nx.cycle_graph(b)
    tf,tn=inter(lambda: nx.modular_product(gn1,gn2), lambda: fnx.modular_product(g1,g2))
    print(f"[{tag}] modular path({a})xcycle({b}): fnx={tf:.1f}ms nx={tn:.1f}ms ratio={tf/tn:.2f}x")
