import time, warnings; warnings.filterwarnings("ignore")
import networkx as nx, franken_networkx as fnx
def wm(fn,n=9):
    ts=[]
    for _ in range(n):
        t0=time.perf_counter(); fn(); ts.append(time.perf_counter()-t0)
    return min(ts)*1000
for nn,frac in ((3000,0.1),(5000,0.2),(8000,0.3)):
    g=fnx.gnp_random_graph(nn,0.005,seed=3); gn=nx.gnp_random_graph(nn,0.005,seed=3)
    S=list(g)[:int(nn*frac)]; Sn=list(gn)[:int(nn*frac)]
    tf=wm(lambda: fnx.node_boundary(g,S)); tn=wm(lambda: nx.node_boundary(gn,Sn))
    print(f"n={nn} |S|={len(S)}: fnx={tf:.3f} nx={tn:.3f} ratio={tf/tn:.2f}x")
