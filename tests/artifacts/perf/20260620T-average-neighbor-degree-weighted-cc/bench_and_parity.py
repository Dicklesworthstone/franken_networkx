"""br-r37-c1-wqhqr (avg_neighbor_degree weighted vectorization).

Run with PYTHONPATH=python. Interleaved min-time timing + exhaustive value
parity fuzz (self-loops, missing weights, empty graphs, all source/target).
"""

from __future__ import annotations

import hashlib
import random
import time

import franken_networkx as fnx
import networkx as nx


def mk(directed, n=1500, p=0.01):
    G = nx.gnp_random_graph(n, p, seed=7, directed=directed)
    r = random.Random(1)
    for u, v in G.edges():
        G[u][v]["weight"] = r.randint(1, 9)
    gf = (fnx.DiGraph if directed else fnx.Graph)()
    for u, v, d in G.edges(data=True):
        gf.add_edge(u, v, **d)
    return gf, G


def interleaved(directed, kw, reps=9):
    gf, G = mk(directed)
    fa = lambda: fnx.average_neighbor_degree(gf, **kw)
    na = lambda: nx.average_neighbor_degree(G, **kw)
    fa(); na()
    bf = bx = 1e9
    for _ in range(reps):
        t = time.perf_counter(); fa(); bf = min(bf, time.perf_counter() - t)
        t = time.perf_counter(); na(); bx = min(bx, time.perf_counter() - t)
    return bf * 1000, bx * 1000


def timings():
    print("== timing (interleaved min-of-9) ==")
    for label, d, kw in [
        ("undir/wt", False, {"weight": "weight"}),
        ("dir/wt in+out", True, {"source": "in+out", "target": "in+out", "weight": "weight"}),
        ("dir/wt in/out", True, {"source": "in", "target": "out", "weight": "weight"}),
        ("dir/wt out/in", True, {"source": "out", "target": "in", "weight": "weight"}),
    ]:
        bf, bx = interleaved(d, kw)
        print(f"{label:16s} {bx/bf:7.3f}x  fnx {bf:7.2f}ms  nx {bx:7.2f}ms")


def parity():
    h = hashlib.sha256()
    opts = ["in", "out", "in+out"]
    checks = fails = 0
    for seed in range(200):
        r = random.Random(seed)
        directed = seed % 2 == 0
        n = r.randint(0, 16)
        G = (nx.DiGraph if directed else nx.Graph)()
        G.add_nodes_from(range(n))
        for _ in range(r.randint(0, n * 2) if n else 0):
            u = r.randrange(n)
            v = r.randrange(n)
            if r.random() < 0.7:
                G.add_edge(u, v, weight=r.randint(1, 9))
            else:
                G.add_edge(u, v)
        gf = (fnx.DiGraph if directed else fnx.Graph)()
        gf.add_nodes_from(range(n))
        for u, v, d in G.edges(data=True):
            gf.add_edge(u, v, **d)
        for s in (opts if directed else ["out"]):
            for t in (opts if directed else ["out"]):
                for w in (None, "weight"):
                    checks += 1
                    a = fnx.average_neighbor_degree(gf, source=s, target=t, weight=w)
                    b = nx.average_neighbor_degree(G, source=s, target=t, weight=w)
                    h.update(repr((seed, s, t, w, sorted(a.items()))).encode())
                    if set(a) != set(b) or any(abs(a[k] - b[k]) > 1e-9 for k in a):
                        fails += 1
                        print("FAIL", seed, directed, s, t, w)
    print(f"== parity: {checks} checks, {fails} fails ==")
    print("golden sha256:", h.hexdigest())
    return fails


if __name__ == "__main__":
    timings()
    raise SystemExit(1 if parity() else 0)
