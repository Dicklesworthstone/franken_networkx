import time, random
import networkx as nx, franken_networkx as fnx

rnd = random.Random(2)
# connected graph: random + a spanning cycle
n = 250
edges = [(i, (i + 1) % n) for i in range(n)] + [
    (rnd.randrange(n), rnd.randrange(n)) for _ in range(900)
]
fg, ng = fnx.Graph(edges), nx.Graph(edges)
assert nx.is_connected(ng)


def t(f, *a):
    best = 1e9
    for _ in range(3):
        s = time.perf_counter()
        f(*a)
        best = min(best, time.perf_counter() - s)
    return best


tf, tn = t(fnx.node_connectivity, fg), t(nx.node_connectivity, ng)
print(f"connected n={n}: fnx={tf*1000:.1f}ms nx={tn*1000:.1f}ms ratio={tf/tn:.2f}x "
      f"value fnx={fnx.node_connectivity(fg)} nx={nx.node_connectivity(ng)}")

# disconnected (the 27x case)
e2 = [(rnd.randrange(1500), rnd.randrange(1500)) for _ in range(1200)]
f2, n2 = fnx.Graph(e2), nx.Graph(e2)
tf, tn = t(fnx.node_connectivity, f2), t(nx.node_connectivity, n2)
print(f"disconnected: fnx={tf*1000:.2f}ms nx={tn*1000:.2f}ms ratio={tf/tn:.2f}x")

# directed
de = [(i, (i + 1) % n) for i in range(n)] + [((i + 7) % n, i) for i in range(n)]
fd, nd = fnx.DiGraph(de), nx.DiGraph(de)
tf, tn = t(fnx.node_connectivity, fd), t(nx.node_connectivity, nd)
print(f"directed: fnx={tf*1000:.1f}ms nx={tn*1000:.1f}ms ratio={tf/tn:.2f}x "
      f"value fnx={fnx.node_connectivity(fd)} nx={nx.node_connectivity(nd)}")
