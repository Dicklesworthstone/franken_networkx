import franken_networkx as fnx
import networkx as nx
from franken_networkx.backend import _fnx_to_nx
from collections import defaultdict


def to_fnx(G):
    H = fnx.Graph(); H.add_nodes_from(G.nodes()); H.add_edges_from(G.edges()); return H


def lpc_inproc(G):
    node_list = list(G)
    n = len(node_list)
    idx = {u: i for i, u in enumerate(node_list)}
    # native key-only adjacency snapshot, index space
    adj = [None] * n
    nak = getattr(G, "_native_adjacency_keys", None)
    if nak is not None:
        for node, nbrs in nak():
            adj[idx[node]] = [idx[v] for v in nbrs]
    else:
        for u in node_list:
            adj[idx[u]] = [idx[v] for v in G._adj[u]]

    # coloring (native greedy_color, nx-order), grouped color->[node idx]
    colors = fnx.coloring.greedy_color(G)  # {node: color}
    color_buckets = {}
    color_order = []
    for u, c in colors.items():  # mirror nx _color_network: greedy_color dict order
        b = color_buckets.get(c)
        if b is None:
            b = []
            color_buckets[c] = b
            color_order.append(c)
        b.append(idx[u])

    labels = list(range(n))
    freq = [0] * n

    def most_frequent(node):
        nbrs = adj[node]
        if not nbrs:
            return None  # caller handles isolated
        touched = []
        for v in nbrs:
            lab = labels[v]
            if freq[lab] == 0:
                touched.append(lab)
            freq[lab] += 1
        mx = freq[touched[0]]
        for l in touched:
            if freq[l] > mx:
                mx = freq[l]
        best = [l for l in touched if freq[l] == mx]
        for l in touched:
            freq[l] = 0
        return best

    def complete():
        for v in range(n):
            if not adj[v]:
                continue
            best = most_frequent(v)
            if labels[v] not in best:
                return False
        return True

    while not complete():
        for c in color_order:
            for node in color_buckets[c]:
                if not adj[node]:
                    continue
                best = most_frequent(node)
                if len(best) == 1:
                    labels[node] = best[0]
                elif len(best) > 1:
                    if labels[node] not in best:
                        labels[node] = max(best)

    clusters = defaultdict(set)
    for i in range(n):
        clusters[labels[i]].add(node_list[i])
    return list(clusters.values())


fails = 0; checks = 0
for seed in range(80):
    for n, p in [(40, 0.1), (80, 0.08), (150, 0.05), (60, 0.15), (200, 0.04), (100, 0.12)]:
        G = nx.gnp_random_graph(n, p, seed=seed)
        H = to_fnx(G); Gnx = _fnx_to_nx(H)
        ref = list(nx.community.label_propagation_communities(Gnx))
        got = lpc_inproc(H)
        checks += 1
        if [tuple(sorted(s)) for s in ref] != [tuple(sorted(s)) for s in got]:
            fails += 1
            if fails <= 6:
                print(f"MISMATCH n={n} p={p} seed={seed}")
                print("  ref", [sorted(s) for s in ref][:3])
                print("  got", [sorted(s) for s in got][:3])
# string-keyed + isolated
for seed in range(25):
    base = nx.gnp_random_graph(50, 0.1, seed=seed)
    G = nx.relabel_nodes(base, {i: f"n{i}" for i in base})
    G.add_nodes_from(["iso1", "iso2"])
    H = to_fnx(G); Gnx = _fnx_to_nx(H)
    ref = list(nx.community.label_propagation_communities(Gnx))
    got = lpc_inproc(H)
    checks += 1
    if [tuple(sorted(map(str, s))) for s in ref] != [tuple(sorted(map(str, s))) for s in got]:
        fails += 1; print(f"STR MISMATCH seed={seed}")
print(f"DONE checks={checks} fails={fails}")
