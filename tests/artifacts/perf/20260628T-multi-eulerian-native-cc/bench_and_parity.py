"""br-r37-c1-mgisol (CopperCliff): native undirected-MultiGraph eulerian
predicates (is_eulerian / has_eulerian_path / is_semieulerian) — drop the full
gr.undirected() projection + per-node Python degree-view crossing.
"""
import time, warnings, random
warnings.filterwarnings("ignore")
import networkx as nx, franken_networkx as fnx

def t(fn, n=8):
    b = 1e9
    for _ in range(n):
        s = time.perf_counter(); r = fn(); b = min(b, time.perf_counter()-s)
    return b*1e3, r

# A connected MultiGraph with parallel edges, NO self-loops (wrapper keeps the
# native binding path), all-even degree where possible -> exercises the full
# parity + connectivity path.
def build_eulerish(C, n, seed):
    random.seed(seed)
    G = C(); G.add_nodes_from(range(n))
    # cycle to guarantee connectivity + even degree
    for i in range(n):
        G.add_edge(i, (i+1) % n)
    # add parallel pairs (keeps all degrees even)
    for _ in range(n):
        u = random.randrange(n)
        G.add_edge(u, (u+1) % n)
        G.add_edge(u, (u+1) % n)
    return G

print("=== HEAD-TO-HEAD: nx vs fnx (min of 8), undirected MultiGraph n=300 ===")
Gn = build_eulerish(nx.MultiGraph, 300, 7)
Gf = build_eulerish(fnx.MultiGraph, 300, 7)
for fname, nf, ff in [
    ("is_eulerian", lambda: nx.is_eulerian(Gn), lambda: fnx.is_eulerian(Gf)),
    ("has_eulerian_path", lambda: nx.has_eulerian_path(Gn), lambda: fnx.has_eulerian_path(Gf)),
    ("is_semieulerian", lambda: nx.is_semieulerian(Gn), lambda: fnx.is_semieulerian(Gf)),
]:
    tn, rn = t(nf); tf, rf = t(ff)
    print(f"  {fname:20s} nx {tn:7.3f}ms fnx {tf:7.3f}ms  {tn/tf:6.2f}x  match={rn==rf}")

print("\n=== PARITY: byte-exact over random multigraphs (parallels, +/- self-loops, +/- isolates) ===")
mism = 0; total = 0
for seed in range(600):
    random.seed(seed)
    n = random.randrange(2, 30)
    Gn = nx.MultiGraph(); Gf = fnx.MultiGraph()
    Gn.add_nodes_from(range(n)); Gf.add_nodes_from(range(n))
    ne = random.randrange(0, n*2)
    es = [(random.randrange(n), random.randrange(n)) for _ in range(ne)]  # may incl self-loops
    Gn.add_edges_from(es); Gf.add_edges_from(es)
    total += 1
    for fn_n, fn_f, tag in [
        (nx.is_eulerian, fnx.is_eulerian, "is_eulerian"),
        (nx.has_eulerian_path, fnx.has_eulerian_path, "has_eulerian_path"),
        (nx.is_semieulerian, fnx.is_semieulerian, "is_semieulerian"),
    ]:
        try: rn = fn_n(Gn)
        except Exception as e: rn = ("ERR", type(e).__name__)
        try: rf = fn_f(Gf)
        except Exception as e: rf = ("ERR", type(e).__name__)
        if rn != rf:
            mism += 1; print(f"  MISMATCH {tag} seed={seed} n={n} nx={rn} fnx={rf} edges={es[:8]}")
print(f"parity: {mism} mismatches over {total} graphs (x3 predicates each)")
