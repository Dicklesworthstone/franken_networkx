import random
import networkx as nx
from networkx.utils import groups, create_py_random_state


def lpa_mark(G, weight=None, seed=None):
    rng = create_py_random_state(seed)
    nl = list(G)
    n = len(nl)
    idx = {u: i for i, u in enumerate(nl)}
    if weight is None:
        adj = [[idx[v] for v in G._adj[u]] for u in nl]
    else:
        adj = [[(idx[v], dd.get(weight, 1)) for v, dd in G._adj[u].items()] for u in nl]
    labels = list(range(n))
    order = list(range(n))
    freq = [0] * n
    cont = True
    while cont:
        cont = False
        perm = order[:]
        rng.shuffle(perm)
        for node in perm:
            nbrs = adj[node]
            if not nbrs:
                continue
            touched = []
            if weight is None:
                for v in nbrs:
                    lab = labels[v]
                    if freq[lab] == 0:
                        touched.append(lab)
                    freq[lab] += 1
            else:
                for v, wt in nbrs:
                    lab = labels[v]
                    if freq[lab] == 0:
                        touched.append(lab)
                    freq[lab] += wt
            max_freq = freq[touched[0]]
            for l in touched:
                if freq[l] > max_freq:
                    max_freq = freq[l]
            cur = labels[node]
            best = [l for l in touched if freq[l] == max_freq]
            for l in touched:
                freq[l] = 0
            if cur not in best:
                labels[node] = rng.choice(best)
                cont = True
    label_by_node = {nl[i]: labels[i] for i in range(n)}
    return list(groups(label_by_node).values())


def run():
    fails = 0; checks = 0
    for seed in range(100):
        for nn, p in [(30, 0.1), (80, 0.05), (150, 0.05), (60, 0.12), (200, 0.04), (300, 0.03)]:
            G = nx.gnp_random_graph(nn, p, seed=seed)
            b = [sorted(s) for s in lpa_mark(G, seed=seed)]
            c = [sorted(s) for s in nx.community.asyn_lpa_communities(G, seed=seed)]
            checks += 1
            if b != c:
                fails += 1
                if fails <= 6:
                    print(f"MISMATCH nn={nn} p={p} seed={seed}")
                    print("  mark", b[:3]); print("  nx  ", c[:3])
    for seed in range(40):
        rng = random.Random(seed)
        G = nx.gnp_random_graph(70, 0.08, seed=seed)
        for u, v in G.edges():
            G[u][v]["weight"] = rng.choice([1.0, 2.0, 3.0])
        b = [sorted(s) for s in lpa_mark(G, weight="weight", seed=seed)]
        c = [sorted(s) for s in nx.community.asyn_lpa_communities(G, weight="weight", seed=seed)]
        checks += 1
        if b != c:
            fails += 1; print(f"WEIGHTED MISMATCH seed={seed}")
    for seed in range(25):
        base = nx.gnp_random_graph(45, 0.1, seed=seed)
        G = nx.relabel_nodes(base, {i: f"n{i}" for i in base})
        b = [sorted(s) for s in lpa_mark(G, seed=seed)]
        c = [sorted(s) for s in nx.community.asyn_lpa_communities(G, seed=seed)]
        checks += 1
        if b != c:
            fails += 1; print(f"STR MISMATCH seed={seed}")
    print(f"DONE checks={checks} fails={fails}")


if __name__ == "__main__":
    run()
