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
g1=fnx.path_graph(120); gn1=nx.path_graph(120); g2=fnx.cycle_graph(100); gn2=nx.cycle_graph(100)
tf,tn=inter(lambda: nx.strong_product(gn1,gn2), lambda: fnx.strong_product(g1,g2))
print(f"[{tag}] strong path120xcycle100: fnx={tf:.1f}ms nx={tn:.1f}ms ratio={tf/tn:.2f}x")
g3=fnx.path_graph(80); gn3=nx.path_graph(80); g4=fnx.cycle_graph(70); gn4=nx.cycle_graph(70)
tf,tn=inter(lambda: nx.lexicographic_product(gn3,gn4), lambda: fnx.lexicographic_product(g3,g4))
print(f"[{tag}] lexico path80xcycle70: fnx={tf:.1f}ms nx={tn:.1f}ms ratio={tf/tn:.2f}x")
