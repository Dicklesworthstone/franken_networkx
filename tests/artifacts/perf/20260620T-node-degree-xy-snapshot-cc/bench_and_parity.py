"""br-r37-c1-wqhqr: node_degree_xy whole-graph snapshot fast path.

Run with PYTHONPATH=python so it loads the in-tree fnx.

Reproduces the gauntlet head-to-head shapes (hub-spoke undirected, directed
fan), measures fnx vs nx (warm, min-of-N), and runs an exhaustive byte-exact
iteration-order parity sweep (str/int keys, directed both orientations,
weighted, multigraph, self-loops, empty/isolated, nodes-subset, random fuzz)
emitting a golden sha over all results.
"""

from __future__ import annotations

import hashlib
import random
import time

import franken_networkx as fnx
import networkx as nx


def build_hub(lib):
    g = lib.Graph()
    for h in range(512):
        for s in range(32):
            g.add_edge(("h", h), ("s", h, s))
    return g


def build_fan(lib):
    g = lib.DiGraph()
    for h in range(512):
        for s in range(32):
            g.add_edge(("h", h), ("f", h, s))
    return g


def bench(fn, *a, **k):
    list(fn(*a, **k))
    best = 1e9
    for _ in range(9):
        t = time.perf_counter()
        r = list(fn(*a, **k))
        best = min(best, time.perf_counter() - t)
    return best * 1000.0, len(r)


def timings():
    print("== timings (min-of-9, warm) ==")
    gf, gx = build_hub(fnx), build_hub(nx)
    bf, nfp = bench(fnx.node_degree_xy, gf)
    bx, _ = bench(nx.node_degree_xy, gx)
    print(f"undir hub512/s32 : fnx {bf:7.2f}ms  nx {bx:7.2f}ms  {bx/bf:.3f}x  ({nfp} pairs)")
    gf, gx = build_fan(fnx), build_fan(nx)
    bf, nfp = bench(fnx.node_degree_xy, gf, x="out", y="in")
    bx, _ = bench(nx.node_degree_xy, gx, x="out", y="in")
    print(f"dir   fan512/f32  : fnx {bf:7.2f}ms  nx {bx:7.2f}ms  {bx/bf:.3f}x  ({nfp} pairs)")


def parity():
    h = hashlib.sha256()
    checks = fails = 0

    def chk(label, a, b):
        nonlocal checks, fails
        checks += 1
        h.update(repr((label, a)).encode())
        if a != b:
            fails += 1
            print("FAIL", label, a[:6], b[:6])

    def mk(lib, edges, cls):
        g = getattr(lib, cls)()
        for e in edges:
            g.add_edge(*e)
        return g

    edges = [("c", "d"), ("a", "b"), ("b", "c"), ("d", "e"), ("a", "c")]
    chk("str", list(fnx.node_degree_xy(mk(fnx, edges, "Graph"))),
        list(nx.node_degree_xy(mk(nx, edges, "Graph"))))
    chk("str-nodes", list(fnx.node_degree_xy(mk(fnx, edges, "Graph"), nodes=["a", "b", "c"])),
        list(nx.node_degree_xy(mk(nx, edges, "Graph"), nodes=["a", "b", "c"])))
    chk("path", list(fnx.node_degree_xy(fnx.path_graph(5))),
        list(nx.node_degree_xy(nx.path_graph(5))))
    chk("complete", list(fnx.node_degree_xy(fnx.complete_graph(4))),
        list(nx.node_degree_xy(nx.complete_graph(4))))
    de = [("a", "b"), ("b", "c"), ("c", "a"), ("a", "d"), ("a", "a")]
    for x, y in (("out", "in"), ("in", "out")):
        chk(f"dir-{x}{y}", list(fnx.node_degree_xy(mk(fnx, de, "DiGraph"), x=x, y=y)),
            list(nx.node_degree_xy(mk(nx, de, "DiGraph"), x=x, y=y)))
    gf, gx = fnx.Graph(), nx.Graph()
    for u, v, w in [("a", "b", 1), ("b", "c", 2), ("c", "a", 3)]:
        gf.add_edge(u, v, weight=w)
        gx.add_edge(u, v, weight=w)
    chk("weight", list(fnx.node_degree_xy(gf, weight="weight")),
        list(nx.node_degree_xy(gx, weight="weight")))
    mg = [("a", "b"), ("a", "b"), ("b", "c"), ("c", "a")]
    chk("mg", list(fnx.node_degree_xy(mk(fnx, mg, "MultiGraph"))),
        list(nx.node_degree_xy(mk(nx, mg, "MultiGraph"))))
    chk("mdg", list(fnx.node_degree_xy(mk(fnx, mg, "MultiDiGraph"), x="out", y="in")),
        list(nx.node_degree_xy(mk(nx, mg, "MultiDiGraph"), x="out", y="in")))
    chk("selfloop", list(fnx.node_degree_xy(fnx.Graph([(0, 0), (0, 1)]))),
        list(nx.node_degree_xy(nx.Graph([(0, 0), (0, 1)]))))
    chk("empty", list(fnx.node_degree_xy(fnx.Graph())), list(nx.node_degree_xy(nx.Graph())))
    gf, gx = fnx.Graph(), nx.Graph()
    gf.add_nodes_from([0, 1, 2])
    gx.add_nodes_from([0, 1, 2])
    chk("isolated", list(fnx.node_degree_xy(gf)), list(nx.node_degree_xy(gx)))

    # random fuzz — simple Graph/DiGraph (fast path) exact order
    for seed in range(60):
        G = nx.gnp_random_graph(random.Random(seed).randint(0, 30), 0.3,
                                seed=seed, directed=seed % 2 == 0)
        gf = (fnx.DiGraph if G.is_directed() else fnx.Graph)()
        for u, v in G.edges():
            gf.add_edge(u, v)
        for x, y in (("out", "in"), ("in", "out")):
            chk(f"fuzz{seed}-{x}{y}", list(fnx.node_degree_xy(gf, x=x, y=y)),
                list(nx.node_degree_xy(G, x=x, y=y)))

    # multigraph fuzz (fallback path) exact order
    for seed in range(30):
        r = random.Random(1000 + seed)
        nodes = [r.choice("abcdefg") for _ in range(r.randint(2, 12))]
        ed = [(r.choice(nodes), r.choice(nodes)) for _ in range(r.randint(0, 30))]
        for cls in ("MultiGraph", "MultiDiGraph"):
            chk(f"mgf{seed}-{cls}", list(fnx.node_degree_xy(mk(fnx, ed, cls), x="out", y="in")),
                list(nx.node_degree_xy(mk(nx, ed, cls), x="out", y="in")))

    print(f"== parity: {checks} checks, {fails} fails ==")
    print("golden sha256:", h.hexdigest())
    return fails


if __name__ == "__main__":
    timings()
    rc = parity()
    raise SystemExit(1 if rc else 0)
