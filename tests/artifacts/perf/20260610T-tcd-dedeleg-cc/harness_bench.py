import time, warnings, sys; warnings.filterwarnings("ignore")
import networkx as nx, franken_networkx as fnx
def wm(fn,n=7):
    ts=[]
    for _ in range(n):
        t0=time.perf_counter(); fn(); ts.append(time.perf_counter()-t0)
    return min(ts)*1000
tag=sys.argv[1] if len(sys.argv)>1 else "?"
for nn in (1000,2000,4000):
    gf=fnx.gn_graph(nn,seed=4); gn=nx.gn_graph(nn,seed=4)
    tf=wm(lambda: fnx.transitive_closure_dag(gf)); tn=wm(lambda: nx.transitive_closure_dag(gn))
    print(f"[{tag}] n={nn}: fnx={tf:.2f}ms nx={tn:.2f}ms ratio={tf/tn:.2f}x")
