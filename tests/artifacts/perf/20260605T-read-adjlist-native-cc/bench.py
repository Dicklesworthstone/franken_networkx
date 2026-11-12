import time, os, random
import networkx as nx
import franken_networkx as fnx

random.seed(42)
g = nx.Graph(); g.add_nodes_from(range(1500))
for u in range(1500):
    for v in range(u+1, min(u+8,1500)):
        if random.random() < 0.5: g.add_edge(u,v)
p = "/data/tmp/bench.adjlist"
nx.write_adjlist(g, p)
print("nodes/edges:", g.number_of_nodes(), g.number_of_edges())

import franken_networkx.readwrite as fnx_rw
def fnx_after(): return fnx.read_adjlist(p)
def fnx_before():  # force delegated path: monkeypatch kernel to None
    return fnx_rw._read_adjlist_via_nx(p, comments="#", delimiter=None,
                                       create_using=cu_inst, nodetype=None, encoding="utf-8")
cu_inst = fnx.Graph()
def nx_read(): return nx.read_adjlist(p)

# sanity: after == before content
a, b = fnx_after(), fnx_before()
assert list(a) == list(b) and list(a.edges()) == list(b.edges()) and {n: list(a[n]) for n in a} == {n: list(b[n]) for n in b}

# interleaved warm min-of-N
best = {"nx": 9e9, "fnx_before": 9e9, "fnx_after": 9e9}
for fn in (nx_read, fnx_before, fnx_after): fn()  # warm
for _ in range(15):
    for name, fn in (("nx", nx_read), ("fnx_before", fnx_before), ("fnx_after", fnx_after)):
        cu_inst = fnx.Graph()
        t = time.perf_counter(); fn(); dt = time.perf_counter() - t
        best[name] = min(best[name], dt)
print({k: f"{v*1000:.3f}ms" for k, v in best.items()})
print(f"before vs nx: {best['fnx_before']/best['nx']:.2f}x | after vs nx: {best['fnx_after']/best['nx']:.2f}x | self-speedup: {best['fnx_before']/best['fnx_after']:.2f}x")

# small file too
g2 = nx.Graph(); g2.add_edges_from((i, i+1) for i in range(50))
p2 = "/data/tmp/bench_small.adjlist"; nx.write_adjlist(g2, p2)
p_orig = p; p = p2
best2 = {"nx": 9e9, "fnx_after": 9e9}
for _ in range(50):
    t=time.perf_counter(); nx.read_adjlist(p2); best2["nx"]=min(best2["nx"], time.perf_counter()-t)
    t=time.perf_counter(); fnx.read_adjlist(p2); best2["fnx_after"]=min(best2["fnx_after"], time.perf_counter()-t)
print("small(50 edges):", {k: f"{v*1e6:.0f}us" for k,v in best2.items()}, f"ratio {best2['fnx_after']/best2['nx']:.2f}x")
