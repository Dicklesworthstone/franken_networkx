"""br-r37-c1-9d98t: average_degree_connectivity directed + weighted fast paths.

Run with PYTHONPATH=python. Measures fnx vs nx (warm, min-of-N) across the
directed/weighted matrix and runs an exhaustive value parity fuzz (self-loops,
missing weights, all source/target combos, empty graphs, directed+undirected),
emitting a golden sha over all results.
"""

from __future__ import annotations

import hashlib
import random
import time

import franken_networkx as fnx
import networkx as nx


def mk(directed, weighted, n=1500, p=0.01):
    G = nx.gnp_random_graph(n, p, seed=7, directed=directed)
    if weighted:
        r = random.Random(1)
        for u, v in G.edges():
            G[u][v]["weight"] = r.randint(1, 9)
    gf = (fnx.DiGraph if directed else fnx.Graph)()
    for u, v, d in G.edges(data=True):
        gf.add_edge(u, v, **d)
    return gf, G


def bench(fn, *a, **k):
    fn(*a, **k)
    best = 1e9
    for _ in range(6):
        t = time.perf_counter()
        fn(*a, **k)
        best = min(best, time.perf_counter() - t)
    return best * 1000.0


def timings():
    print("== timings (min-of-6, warm) ==")
    cases = [
        ("undir/unw", dict(directed=False, weighted=False), {}),
        ("undir/wt", dict(directed=False, weighted=True), {"weight": "weight"}),
        ("dir/unw in+out", dict(directed=True, weighted=False), {}),
        ("dir/unw in/out", dict(directed=True, weighted=False), {"source": "in", "target": "out"}),
        ("dir/unw out/in", dict(directed=True, weighted=False), {"source": "out", "target": "in"}),
        ("dir/wt in+out", dict(directed=True, weighted=True), {"weight": "weight"}),
        ("dir/wt in/out", dict(directed=True, weighted=True), {"source": "in", "target": "out", "weight": "weight"}),
        ("dir/wt out/in", dict(directed=True, weighted=True), {"source": "out", "target": "in", "weight": "weight"}),
    ]
    for label, g, kw in cases:
        gf, G = mk(**g)
        bf = bench(fnx.average_degree_connectivity, gf, **kw)
        bx = bench(nx.average_degree_connectivity, G, **kw)
        print(f"{label:18s} {bx/bf:7.3f}x  fnx {bf:8.2f}ms  nx {bx:7.2f}ms")


def parity():
    h = hashlib.sha256()
    checks = fails = 0
    opts = ["in", "out", "in+out"]
    for seed in range(150):
        r = random.Random(seed)
        directed = seed % 2 == 0
        n = r.randint(0, 18)
        G = (nx.DiGraph if directed else nx.Graph)()
        G.add_nodes_from(range(n))
        for _ in range(r.randint(0, n * 2) if n else 0):
            u = r.randrange(n)
            v = r.randrange(n)
            if r.random() < 0.7:
                G.add_edge(u, v, weight=r.randint(1, 9))
            else:
                G.add_edge(u, v)  # missing weight -> default 1
        gf = (fnx.DiGraph if directed else fnx.Graph)()
        gf.add_nodes_from(range(n))
        for u, v, d in G.edges(data=True):
            gf.add_edge(u, v, **d)
        srcs = opts if directed else ["in+out"]
        tgts = opts if directed else ["in+out"]
        for s in srcs:
            for t in tgts:
                for w in (None, "weight"):
                    checks += 1
                    try:
                        a = fnx.average_degree_connectivity(gf, source=s, target=t, weight=w)
                    except Exception as e:
                        a = ("ERR", type(e).__name__)
                    try:
                        b = nx.average_degree_connectivity(G, source=s, target=t, weight=w)
                    except Exception as e:
                        b = ("ERR", type(e).__name__)
                    h.update(repr((seed, s, t, w, sorted(a.items()) if isinstance(a, dict) else a)).encode())
                    if isinstance(a, tuple) or isinstance(b, tuple):
                        if a != b:
                            fails += 1
                            print("ERRMISMATCH", seed, s, t, w, a, b)
                        continue
                    if set(a) != set(b) or any(abs(a[k] - b[k]) > 1e-9 for k in a):
                        fails += 1
                        print("FAIL", seed, directed, s, t, w)
    print(f"== parity: {checks} checks, {fails} fails ==")
    print("golden sha256:", h.hexdigest())
    return fails


if __name__ == "__main__":
    timings()
    rc = parity()
    raise SystemExit(1 if rc else 0)
