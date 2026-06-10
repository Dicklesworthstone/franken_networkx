import time, warnings
warnings.filterwarnings("ignore")
import networkx as nx
import franken_networkx as fnx
import itertools as _itertools

# Reconstruct both snapshot strategies sharing the rest of the algorithm.
def impl(G, use_native):
    if use_native:
        nak = G._native_adjacency_keys
        adj = {node: dict.fromkeys(nbrs) for node, nbrs in nak()}
    else:
        adj = {node: nbrs for node, nbrs in G.adjacency()}
    nbunch_lookup = dict.fromkeys(G)
    node_to_id = {node: index for index, node in enumerate(nbunch_lookup)}
    out = []
    for u in nbunch_lookup:
        u_id = node_to_id[u]
        u_neighbors = adj[u].keys()
        for v in u_neighbors:
            v_id = node_to_id.get(v, -1)
            if v_id <= u_id:
                continue
            v_neighbors = adj[v].keys()
            for w in v_neighbors & u_neighbors:
                if node_to_id.get(w, -1) > v_id:
                    out.append((u, v, w))
    return out

def bench(fn, *a, n=10):
    ts = []
    for _ in range(n):
        t0 = time.perf_counter(); fn(*a); ts.append(time.perf_counter()-t0)
    return min(ts)*1000

for n in (300, 500, 800):
    g = fnx.watts_strogatz_graph(n, 6, 0.1, seed=7)
    gn = nx.watts_strogatz_graph(n, 6, 0.1, seed=7)
    # correctness: identical between strategies
    assert impl(g, True) == impl(g, False)
    t_old = bench(impl, g, False)
    t_new = bench(impl, g, True)
    t_nx = bench(lambda gg: list(nx.all_triangles(gg)), gn)
    print(f"n={n}: nx={t_nx:.3f} old(adjacency)={t_old:.3f} ({t_old/t_nx:.2f}x) new(native_keys)={t_new:.3f} ({t_new/t_nx:.2f}x)")
