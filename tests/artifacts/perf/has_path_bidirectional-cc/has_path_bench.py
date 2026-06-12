import franken_networkx as fnx
import networkx as nx
import time, random
random.seed(7)

def bench(fn, *a, N=2000):
    # warmup
    for _ in range(50): fn(*a)
    best = 1e9
    for _ in range(7):
        t=time.perf_counter()
        for _ in range(N): fn(*a)
        best=min(best,(time.perf_counter()-t)/N)
    return best*1e6  # us

scenarios = []
# 1. direct neighbor on dense (K-like): target is adjacent neighbor
Gd = nx.complete_graph(801)
scenarios.append(("dense complete801 neighbor", Gd, 0, 5))
# 2. far target on long sparse path
Gp = nx.path_graph(2000)
scenarios.append(("path2000 far 0->1999", Gp, 0, 1999))
# 3. gnp medium, random reachable
Gg = nx.gnp_random_graph(1000, 0.01, seed=1)
scenarios.append(("gnp1000 p.01", Gg, 0, 500))
# 4. unreachable across components
Gx = nx.disjoint_union(nx.path_graph(1000), nx.path_graph(1000))
scenarios.append(("disconnected 0->1500", Gx, 0, 1500))

for name, G, s, t in scenarios:
    Gf = fnx.Graph(G)
    # ensure nodes exist
    tx = bench(nx.has_path, G, s, t)
    tf = bench(fnx.has_path, Gf, s, t)
    print(f"{name:34s} nx={tx:9.3f}us fnx={tf:9.3f}us  ratio nx/fnx={tx/tf:6.2f}x  (fnx {'FASTER' if tf<tx else 'slower'})")
