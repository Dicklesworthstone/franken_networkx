import time, warnings, sys; warnings.filterwarnings("ignore")
import networkx as nx, franken_networkx as fnx
def wm(fn,n=9):
    ts=[]
    for _ in range(n):
        t0=time.perf_counter(); fn(); ts.append(time.perf_counter()-t0)
    return min(ts)*1000
tag=sys.argv[1] if len(sys.argv)>1 else "?"
for n in (3000,6000,10000):
    gf=fnx.gnp_random_graph(n,0.01,seed=3); gn=nx.gnp_random_graph(n,0.01,seed=3)
    tf=wm(lambda: fnx.node_connected_component(gf,0)); tn=wm(lambda: nx.node_connected_component(gn,0))
    print(f"[{tag}] n={n} E={gf.number_of_edges()}: fnx={tf:.3f}ms nx={tn:.3f}ms ratio={tf/tn:.2f}x")
