import time, warnings, sys, os; warnings.filterwarnings("ignore")
os.environ["NETWORKX_AUTOMATIC_BACKENDS"]=""
import networkx as nx, franken_networkx as fnx
try: nx.config.backend_priority=[]
except Exception: pass
def inter(a,b,n=8):
    fa=[]; fb=[]
    for _ in range(n):
        t0=time.perf_counter(); a(); fa.append(time.perf_counter()-t0)
        t0=time.perf_counter(); b(); fb.append(time.perf_counter()-t0)
    return min(fb)*1000, min(fa)*1000
tag=sys.argv[1]
import warnings as _w; _w.simplefilter("ignore")
for nn,p in ((600,0.04),(1000,0.03),(1500,0.02)):
    gf=fnx.gnp_random_graph(nn,p,seed=3); gn=nx.gnp_random_graph(nn,p,seed=3)
    with _w.catch_warnings():
        _w.simplefilter("ignore")
        tf,tn=inter(lambda: nx.weisfeiler_lehman_graph_hash(gn), lambda: fnx.weisfeiler_lehman_graph_hash(gf))
        tf2,tn2=inter(lambda: nx.weisfeiler_lehman_subgraph_hashes(gn), lambda: fnx.weisfeiler_lehman_subgraph_hashes(gf))
    print(f"[{tag}] n={nn}: hash fnx={tf:.2f} nx={tn:.2f} ({tf/tn:.2f}x) | subhash fnx={tf2:.2f} nx={tn2:.2f} ({tf2/tn2:.2f}x)")
