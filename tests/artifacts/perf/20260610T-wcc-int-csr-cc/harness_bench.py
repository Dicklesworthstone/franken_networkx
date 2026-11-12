import time, warnings, sys; warnings.filterwarnings("ignore")
import networkx as nx, franken_networkx as fnx
def wm(fn,n=9):
    ts=[]
    for _ in range(n):
        t0=time.perf_counter(); fn(); ts.append(time.perf_counter()-t0)
    return min(ts)*1000
tag=sys.argv[1] if len(sys.argv)>1 else "?"
for n,p in ((1500,0.05),(3000,0.01),(5000,0.004)):
    gf=fnx.gnp_random_graph(n,p,seed=3,directed=True); gn=nx.gnp_random_graph(n,p,seed=3,directed=True)
    tf=wm(lambda: list(fnx.weakly_connected_components(gf)))
    tn=wm(lambda: list(nx.weakly_connected_components(gn)))
    print(f"[{tag}] n={n} E={gf.number_of_edges()}: fnx={tf:.3f}ms nx={tn:.3f}ms ratio={tf/tn:.2f}x")
