import random
from collections import deque
import networkx as nx
from networkx.utils import groups, create_py_random_state


def flpa_idx(G, weight=None, seed=None):
    # simple undirected Graph, weight=None
    rng = create_py_random_state(seed)
    nl = list(G)
    n = len(nl)
    idx = {u: i for i, u in enumerate(nl)}
    adj = [[idx[v] for v in G._adj[u]] for u in nl]
    comms = list(range(n))
    perm = list(range(n))
    rng.shuffle(perm)            # O(n); same permutation as shuffling deque(G)
    queue = deque(perm)
    in_queue = [True] * n        # bool array == nodes_set membership
    freq = [0] * n
    while queue:
        node = queue.popleft()
        in_queue[node] = False
        nbrs = adj[node]
        if nbrs:
            touched = []
            for v in nbrs:
                lab = comms[v]
                if freq[lab] == 0:
                    touched.append(lab)
                freq[lab] += 1
            max_freq = freq[touched[0]]
            for l in touched:
                if freq[l] > max_freq:
                    max_freq = freq[l]
            best = [l for l in touched if freq[l] == max_freq]
            for l in touched:
                freq[l] = 0
            comm = rng.choice(best)
            if comms[node] != comm:
                comms[node] = comm
                for v in nbrs:
                    if comms[v] != comm and not in_queue[v]:
                        queue.append(v)
                        in_queue[v] = True
    label_by_node = {nl[i]: comms[i] for i in range(n)}
    return list(groups(label_by_node).values())


def run():
    fails = 0; checks = 0
    for seed in range(100):
        for nn, p in [(30, 0.1), (80, 0.05), (150, 0.05), (60, 0.12), (200, 0.04), (300, 0.04)]:
            G = nx.gnp_random_graph(nn, p, seed=seed)
            b = [sorted(s) for s in flpa_idx(G, seed=seed)]
            c = [sorted(s) for s in nx.community.fast_label_propagation_communities(G, seed=seed)]
            checks += 1
            if b != c:
                fails += 1
                if fails <= 6:
                    print(f"MISMATCH nn={nn} p={p} seed={seed}")
                    print("  idx", b[:3]); print("  nx ", c[:3])
    # string-keyed
    for seed in range(30):
        base = nx.gnp_random_graph(45, 0.1, seed=seed)
        G = nx.relabel_nodes(base, {i: f"n{i}" for i in base})
        b = [sorted(s) for s in flpa_idx(G, seed=seed)]
        c = [sorted(s) for s in nx.community.fast_label_propagation_communities(G, seed=seed)]
        checks += 1
        if b != c:
            fails += 1; print(f"STR MISMATCH seed={seed}")
    # graph with isolated nodes
    for seed in range(20):
        G = nx.gnp_random_graph(50, 0.05, seed=seed)
        G.add_nodes_from([100, 101, 102])  # isolated
        b = [sorted(s) for s in flpa_idx(G, seed=seed)]
        c = [sorted(s) for s in nx.community.fast_label_propagation_communities(G, seed=seed)]
        checks += 1
        if b != c:
            fails += 1; print(f"ISO MISMATCH seed={seed}")
    print(f"DONE checks={checks} fails={fails}")


if __name__ == "__main__":
    run()
