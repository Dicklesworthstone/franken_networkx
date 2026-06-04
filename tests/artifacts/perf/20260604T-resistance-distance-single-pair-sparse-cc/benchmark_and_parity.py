import sys, time, random, math
sys.path.insert(0, "/data/projects/franken_networkx/python")
import numpy as np, networkx as nx, importlib
fnx = importlib.import_module("franken_networkx")
import franken_networkx as F
np.seterr(all="ignore")


def cp(Gx):
    Gf = fnx.Graph(); Gf.add_nodes_from(Gx.nodes()); Gf.add_edges_from(Gx.edges(data=True)); return Gf


# --- parity: all shapes, weighted/unweighted/invert ---
maxerr = 0.0; nbad = 0
for seed in range(40):
    rnd = random.Random(seed)
    n = rnd.randint(3, 35)
    Gx = nx.connected_watts_strogatz_graph(max(4, n), 4, 0.35, seed=seed)
    weighted = seed % 2 == 0
    if weighted:
        for u, v in Gx.edges():
            Gx[u][v]["weight"] = rnd.uniform(0.5, 5.0)
    Gf = cp(Gx)
    wk = "weight" if weighted else None
    nl = list(Gx.nodes())
    for invert in (True, False):
        # single pairs
        for _ in range(5):
            a, b = rnd.choice(nl), rnd.choice(nl)
            ra = nx.resistance_distance(Gx, a, b, weight=wk, invert_weight=invert)
            rb = fnx.resistance_distance(Gf, a, b, weight=wk, invert_weight=invert)
            if abs(ra - rb) > 1e-6: nbad += 1
            maxerr = max(maxerr, abs(ra - rb))
        # nodeA-only dict
        a = nl[0]
        da = nx.resistance_distance(Gx, a, None, weight=wk, invert_weight=invert)
        db = fnx.resistance_distance(Gf, a, None, weight=wk, invert_weight=invert)
        maxerr = max(maxerr, max(abs(da[k] - db[k]) for k in da))
print(f"PARITY all-shapes: max_err={maxerr:.2e} bad={nbad}  {'PASS' if nbad==0 and maxerr<1e-6 else 'FAIL'}")

# same-node returns 0
G2 = cp(nx.path_graph(5))
assert fnx.resistance_distance(G2, 2, 2) == 0.0

# --- benchmark single-pair: new sparse vs old dense pinv (force fallback) ---
orig = F._resistance_single_pair_sparse
def timeit(fn, reps=3):
    best = float("inf")
    for _ in range(reps):
        s = time.perf_counter(); fn(); best = min(best, time.perf_counter()-s)
    return best
for n in (300, 800, 1500):
    Gx = nx.connected_watts_strogatz_graph(n, 6, 0.3, seed=7)
    Gf = cp(Gx)
    a, b = 0, n // 2
    F._resistance_single_pair_sparse = orig
    fnx.resistance_distance(Gf, a, b)  # warm
    tnew = timeit(lambda: fnx.resistance_distance(Gf, a, b))
    F._resistance_single_pair_sparse = lambda *aa, **kk: None  # force dense pinv
    told = timeit(lambda: fnx.resistance_distance(Gf, a, b))
    F._resistance_single_pair_sparse = orig
    print(f"n={n:5d}  dense_pinv={told:8.4f}s  sparse_solve={tnew:7.4f}s  speedup={told/tnew:6.1f}x", flush=True)
