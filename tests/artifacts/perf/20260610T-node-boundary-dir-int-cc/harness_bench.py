import time, warnings, sys; warnings.filterwarnings("ignore")
import networkx as nx, franken_networkx as fnx
def wm(fn,n=9):
    ts=[]
    for _ in range(n):
        t0=time.perf_counter(); fn(); ts.append(time.perf_counter()-t0)
    return min(ts)*1000
tag=sys.argv[1] if len(sys.argv)>1 else "?"
for nn,frac in ((2500,0.24),(5000,0.2),(8000,0.3)):
    g=fnx.gnp_random_graph(nn,0.004,seed=3,directed=True); gn=nx.gnp_random_graph(nn,0.004,seed=3,directed=True)
    S=list(g)[:int(nn*frac)]; Sn=list(gn)[:int(nn*frac)]
    tf=wm(lambda: fnx.node_boundary(g,S)); tn=wm(lambda: nx.node_boundary(gn,Sn))
    print(f"[{tag}] n={nn} |S|={len(S)}: fnx={tf:.3f}ms nx={tn:.3f}ms ratio={tf/tn:.2f}x")
