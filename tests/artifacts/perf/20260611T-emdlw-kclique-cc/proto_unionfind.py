import time
from itertools import combinations
import franken_networkx as fnx
import networkx as nx
import networkx.algorithms.community as nxc
from franken_networkx.backend import _fnx_to_nx


def to_fnx(G):
    H = fnx.Graph(); H.add_nodes_from(G.nodes()); H.add_edges_from(G.edges()); return H


def kclique_uf(G, k, cliques=None):
    if cliques is None:
        cliques = fnx.find_cliques(G)
    clique_list = [frozenset(c) for c in cliques if len(c) >= k]
    m = len(clique_list)
    parent = list(range(m))

    def find(x):
        root = x
        while parent[root] != root:
            root = parent[root]
        while parent[x] != root:
            parent[x], x = root, parent[x]
        return root

    km1 = k - 1
    # group clique indices by each (k-1)-subset; union consecutive members
    subset_first = {}
    for i, clique in enumerate(clique_list):
        for sub in combinations(sorted(clique), km1):
            j = subset_first.get(sub)
            if j is None:
                subset_first[sub] = i
            else:
                ri, rj = find(i), find(j)
                if ri != rj:
                    parent[ri] = rj
    # emit components in first-clique-index order (== nx connected_components)
    root_nodes = {}
    order = []
    for i in range(m):
        r = find(i)
        bucket = root_nodes.get(r)
        if bucket is None:
            bucket = set()
            root_nodes[r] = bucket
            order.append(r)
        bucket |= clique_list[i]
    return [frozenset(root_nodes[r]) for r in order]


fails = 0; checks = 0
for seed in range(80):
    for n, p in [(40, 0.15), (80, 0.1), (120, 0.08), (200, 0.05), (60, 0.2), (100, 0.12)]:
        for k in (2, 3, 4, 5):
            G = nx.gnp_random_graph(n, p, seed=seed)
            H = to_fnx(G); Gnx = _fnx_to_nx(H)
            ref = list(nxc.k_clique_communities(Gnx, k))
            got = kclique_uf(H, k)
            checks += 1
            if [tuple(sorted(s)) for s in ref] != [tuple(sorted(s)) for s in got]:
                fails += 1
                if fails <= 6:
                    print(f"MISMATCH n={n} p={p} seed={seed} k={k}")
                    print("  ref", [sorted(s) for s in ref][:2])
                    print("  got", [sorted(s) for s in got][:2])
print(f"UF k_clique: checks={checks} fails={fails}")

# bench at the bead's size
G = nx.gnp_random_graph(300, 0.04, seed=3); H = to_fnx(G); Gnx = _fnx_to_nx(H)


def bench(fn, reps=9, inner=3):
    best = []
    for _ in range(reps):
        ts = []
        for _ in range(inner):
            t0 = time.perf_counter(); fn(); ts.append(time.perf_counter() - t0)
        best.append(min(ts))
    return min(best)


uf = bench(lambda: kclique_uf(H, 3))
nn = bench(lambda: list(nxc.k_clique_communities(Gnx, 3)))
print(f"UF {uf*1000:.3f}ms  nx {nn*1000:.3f}ms  uf/nx {uf/nn:.3f}x")
# also a denser/larger graph
G2 = nx.gnp_random_graph(500, 0.05, seed=9); H2 = to_fnx(G2); G2nx = _fnx_to_nx(H2)
uf2 = bench(lambda: kclique_uf(H2, 3)); nn2 = bench(lambda: list(nxc.k_clique_communities(G2nx, 3)))
print(f"n500: UF {uf2*1000:.3f}ms  nx {nn2*1000:.3f}ms  uf/nx {uf2/nn2:.3f}x")
