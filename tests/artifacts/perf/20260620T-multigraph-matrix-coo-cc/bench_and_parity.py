"""br-r37-c1-iyu0a: route multigraph to_numpy_array / to_scipy_sparse_array
(default weight='weight', dtype=None) through the existing native COO kernel.

Run with PYTHONPATH=python. Interleaved timing + exhaustive value/dtype parity
(int/float/missing weights, self-loops, MultiGraph + MultiDiGraph).
"""

from __future__ import annotations

import hashlib
import random
import time

import franken_networkx as fnx
import networkx as nx
import numpy as np


def build(kind, seed, n, p, intw=True, missing=False, selfloop=False):
    base = nx.gnp_random_graph(n, p, seed=seed, directed="Di" in kind)
    r = random.Random(seed)
    Gx = getattr(nx, kind)()
    Gf = getattr(fnx, kind)()
    for g in (Gx, Gf):
        g.add_nodes_from(range(n))

    def w():
        return r.randint(1, 9) if intw else round(r.random() * 5, 3)

    for u, v in base.edges():
        skip = missing and r.random() < 0.3
        w1 = None if skip else w()
        for g in (Gx, Gf):
            g.add_edge(u, v) if w1 is None else g.add_edge(u, v, weight=w1)
        if r.random() < 0.4:
            w2 = w()
            for g in (Gx, Gf):
                g.add_edge(u, v, weight=w2)
    if selfloop:
        for g in (Gx, Gf):
            g.add_edge(0, 0, weight=3)
    return Gf, Gx


def il(ff, fn, reps=15):
    ff(); fn()
    bf = bx = 1e9
    for _ in range(reps):
        t = time.perf_counter(); ff(); bf = min(bf, time.perf_counter() - t)
        t = time.perf_counter(); fn(); bx = min(bx, time.perf_counter() - t)
    return bf * 1000, bx * 1000


def timings():
    print("== timing (interleaved min-of-15; n=500, p=0.02) ==")
    for kind in ("MultiGraph", "MultiDiGraph"):
        Gf, Gx = build(kind, 3, 500, 0.02)
        bf, bx = il(lambda: fnx.to_numpy_array(Gf, weight="weight"),
                    lambda: nx.to_numpy_array(Gx, weight="weight"))
        print(f"to_numpy {kind:13s}: {bx/bf:.3f}x  fnx {bf:.2f}ms  nx {bx:.2f}ms")
        bf, bx = il(lambda: fnx.to_scipy_sparse_array(Gf, weight="weight"),
                    lambda: nx.to_scipy_sparse_array(Gx, weight="weight"))
        print(f"to_scipy {kind:13s}: {bx/bf:.3f}x  fnx {bf:.2f}ms  nx {bx:.2f}ms")


def parity():
    h = hashlib.sha256()
    checks = fails = 0
    for kind in ("MultiGraph", "MultiDiGraph"):
        for intw in (True, False):
            for missing in (False, True):
                for selfloop in (False, True):
                    for wt in ("weight", None):
                        for seed in range(5):
                            checks += 1
                            Gf, Gx = build(kind, seed, 30, 0.3, intw, missing, selfloop)
                            A = fnx.to_numpy_array(Gf, weight=wt)
                            B = nx.to_numpy_array(Gx, weight=wt)
                            S = fnx.to_scipy_sparse_array(Gf, weight=wt)
                            T = nx.to_scipy_sparse_array(Gx, weight=wt)
                            h.update(A.tobytes())
                            ok = (A.shape == B.shape and np.allclose(A, B)
                                  and A.dtype == B.dtype
                                  and (S != T).nnz == 0 and S.dtype == T.dtype)
                            if not ok:
                                fails += 1
                                print("FAIL", kind, intw, missing, selfloop, wt, seed,
                                      A.dtype, B.dtype)
    print(f"== parity: {checks} configs x2 exporters, {fails} fails ==")
    print("golden sha256:", h.hexdigest())
    return fails


if __name__ == "__main__":
    timings()
    raise SystemExit(1 if parity() else 0)
