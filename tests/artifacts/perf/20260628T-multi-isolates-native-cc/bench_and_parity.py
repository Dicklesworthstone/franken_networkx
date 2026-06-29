"""br-r37-c1-mgisol (CopperCliff): native Multi isolates/number_of_isolates/
is_isolate — drop the per-call simple-graph projection.

Bench: head-to-head vs NetworkX. Parity: byte-exact over random multigraphs
incl. isolates, self-loops, parallel edges.
"""
import time, warnings, random
warnings.filterwarnings("ignore")
import networkx as nx, franken_networkx as fnx

def t(fn, n=8):
    b = 1e9
    for _ in range(n):
        s = time.perf_counter(); r = fn(); b = min(b, time.perf_counter()-s)
    return b*1e3, r

def build(C, n, m, isolates_n, seed):
    random.seed(seed)
    G = C(); G.add_nodes_from(range(n))
    base = [(random.randrange(n-isolates_n), random.randrange(n-isolates_n)) for _ in range(m)]
    base += base[:m//5]              # parallels
    base += [(0,0),(1,1)]            # self-loops (node 0,1 NOT isolated)
    G.add_edges_from(base)
    G.add_nodes_from(range(n, n+isolates_n))  # true isolates
    return G

print("=== HEAD-TO-HEAD: nx vs fnx (min of 8) ===")
for cls_n, cls_f, name in [(nx.MultiGraph, fnx.MultiGraph, "MultiGraph"),
                            (nx.MultiDiGraph, fnx.MultiDiGraph, "MultiDiGraph")]:
    Gn = build(cls_n, 200, 1000, 20, 13)
    Gf = build(cls_f, 200, 1000, 20, 13)
    for fname in ["number_of_isolates", "isolates", "is_isolate"]:
        if fname == "is_isolate":
            fn_n = lambda: nx.is_isolate(Gn, 5);  fn_f = lambda: fnx.is_isolate(Gf, 5)
        elif fname == "isolates":
            fn_n = lambda: list(nx.isolates(Gn)); fn_f = lambda: list(fnx.isolates(Gf))
        else:
            fn_n = lambda: nx.number_of_isolates(Gn); fn_f = lambda: fnx.number_of_isolates(Gf)
        tn, rn = t(fn_n); tf, rf = t(fn_f)
        print(f"  {name:13s} {fname:20s} nx {tn:7.3f}ms fnx {tf:7.3f}ms  {tn/tf:6.2f}x  match={rn==rf}")

print("\n=== PARITY: byte-exact over random multigraphs (isolates+selfloops+parallels) ===")
mism = 0; total = 0
for seed in range(400):
    random.seed(seed)
    n = random.randrange(4, 40)
    for cls_n, cls_f in [(nx.MultiGraph, fnx.MultiGraph), (nx.MultiDiGraph, fnx.MultiDiGraph)]:
        Gn = cls_n(); Gf = cls_f()
        Gn.add_nodes_from(range(n)); Gf.add_nodes_from(range(n))
        ne = random.randrange(0, n*2)
        es = [(random.randrange(n), random.randrange(n)) for _ in range(ne)]
        Gn.add_edges_from(es); Gf.add_edges_from(es)
        total += 1
        if list(nx.isolates(Gn)) != list(fnx.isolates(Gf)): mism += 1; print("ISO MISMATCH", seed)
        if nx.number_of_isolates(Gn) != fnx.number_of_isolates(Gf): mism += 1; print("NOI MISMATCH", seed)
        for node in range(n):
            if nx.is_isolate(Gn, node) != fnx.is_isolate(Gf, node): mism += 1; print("ISISO MISMATCH", seed, node)
print(f"parity: {mism} mismatches over {total} graphs (x3 checks each)")
