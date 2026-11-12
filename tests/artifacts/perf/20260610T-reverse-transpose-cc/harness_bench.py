import time, warnings, sys
warnings.filterwarnings("ignore")
import networkx as nx
import franken_networkx as fnx

def warm_min(fn, n=9):
    ts = []
    for _ in range(n):
        t0 = time.perf_counter(); fn(); ts.append(time.perf_counter()-t0)
    return min(ts)*1000

tag = sys.argv[1] if len(sys.argv) > 1 else "?"
for n in (800, 1500, 2500):
    gf = fnx.gnp_random_graph(n, 0.05, seed=3, directed=True)
    gn = nx.gnp_random_graph(n, 0.05, seed=3, directed=True)
    tf = warm_min(lambda: gf.reverse())
    tnx = warm_min(lambda: gn.reverse())
    e = gf.number_of_edges()
    print(f"[{tag}] n={n} E={e}: fnx={tf:.2f}ms nx={tnx:.2f}ms ratio={tf/tnx:.2f}x")
