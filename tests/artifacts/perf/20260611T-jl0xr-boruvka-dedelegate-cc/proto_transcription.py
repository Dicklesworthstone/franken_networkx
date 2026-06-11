"""Validate the in-process boruvka transcription against nx.boruvka_mst_edges
on plain nx graphs (algorithm correctness, independent of fnx)."""
import random
import networkx as nx
from networkx.utils import UnionFind
from math import isnan


def inproc_boruvka(G, weight, minimum, ignore_nan):
    sign = 1 if minimum else -1
    adj = {}
    for n in G:
        row = []
        for nbr, dd in G._adj[n].items():
            w = dd.get(weight, 1)
            if not isinstance(w, (int, float)) or isinstance(w, bool):
                return None
            w = w * sign
            if isnan(w):
                if ignore_nan:
                    continue
                return None
            row.append((nbr, w))
        adj[n] = row

    forest = UnionFind(G)

    def best_for(component):
        cset = {n for n in component}
        best = None
        bw = float("inf")
        for n in cset:
            for nbr, w in adj[n]:
                if nbr in cset:
                    continue
                if w < bw:
                    bw = w
                    best = (n, nbr)
        return best

    out = []
    while True:
        best_edges = []
        for comp in forest.to_sets():
            be = best_for(comp)
            if be is not None:
                best_edges.append(be)
        if not best_edges:
            break
        for u, v in best_edges:
            if forest[u] != forest[v]:
                out.append((u, v))
                forest.union(u, v)
    return out


def run_cases():
    fails = 0
    cfgs = []
    for seed in range(40):
        for n, m in [(20, 40), (50, 120), (100, 300), (8, 12), (200, 800)]:
            cfgs.append((n, m, seed))
    for n, m, seed in cfgs:
        rng = random.Random(seed * 7 + 1)
        G = nx.gnm_random_graph(n, m, seed=seed)
        for u, v in G.edges():
            G[u][v]["weight"] = rng.random()
        for minimum in (True, False):
            ref = [(u, v) for u, v, d in nx.minimum_spanning_edges(
                G, algorithm="boruvka", weight="weight", data=True)] if minimum else \
                [(u, v) for u, v, d in nx.maximum_spanning_edges(
                G, algorithm="boruvka", weight="weight", data=True)]
            got = inproc_boruvka(G, "weight", minimum, False)
            if got != ref:
                fails += 1
                if fails <= 5:
                    print(f"MISMATCH n={n} m={m} seed={seed} minimum={minimum}")
                    print("  ref", ref[:10])
                    print("  got", got[:10])
    # also test string-keyed / tuple-keyed nodes
    for seed in range(20):
        rng = random.Random(seed)
        base = nx.gnm_random_graph(30, 70, seed=seed)
        G = nx.Graph()
        mapping = {i: f"node_{i}" for i in base}
        G.add_nodes_from(mapping[i] for i in base)
        for u, v in base.edges():
            G.add_edge(mapping[u], mapping[v], weight=rng.random())
        ref = [(u, v) for u, v, d in nx.minimum_spanning_edges(
            G, algorithm="boruvka", weight="weight", data=True)]
        got = inproc_boruvka(G, "weight", True, False)
        if got != ref:
            fails += 1
            print(f"STR MISMATCH seed={seed}")
            print("  ref", ref[:8])
            print("  got", got[:8])
    print(f"DONE fails={fails}")


if __name__ == "__main__":
    run_cases()
