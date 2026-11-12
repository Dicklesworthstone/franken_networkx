import sys, hashlib, json, random, math
sys.path.insert(0, "/data/projects/franken_networkx/python")
import numpy as np, networkx as nx, importlib
fnx = importlib.import_module("franken_networkx")
import franken_networkx as F
np.seterr(all="ignore")


def cp(Gx):
    Gf = fnx.Graph(); Gf.add_nodes_from(Gx.nodes()); Gf.add_edges_from(Gx.edges(data=True)); return Gf


def corpus():
    out = []
    for seed in range(25):
        rnd = random.Random(1000 + seed)
        n = rnd.randint(3, 55)
        Gx = nx.connected_watts_strogatz_graph(max(4, n), 4, 0.35, seed=seed)
        for u, v in Gx.edges():
            Gx[u][v]["weight"] = round(rnd.uniform(0.3, 6.0), 4)
        out.append((Gx, cp(Gx)))
    return out


def digest(results):
    # round to 8 decimals so the rounding-equivalent Woodbury reformulation
    # produces a stable golden digest; NaN canonicalized.
    h = hashlib.sha256()
    for r in results:
        items = []
        for k in r:
            v = r[k]
            items.append((str(k), "nan" if math.isnan(v) else round(v, 8)))
        h.update(json.dumps(items, sort_keys=False).encode())
    return h.hexdigest()


C = corpus()
orig = F._second_order_fundamental_columns

# new (Woodbury)
F._second_order_fundamental_columns = orig
new = [fnx.second_order_centrality(Gf, weight="weight") for _, Gf in C]
# old (exact O(n^4) loop, forced)
F._second_order_fundamental_columns = lambda *a, **k: None
old = [fnx.second_order_centrality(Gf, weight="weight") for _, Gf in C]
F._second_order_fundamental_columns = orig
# networkx reference
ref = [nx.second_order_centrality(Gx, weight="weight") for Gx, _ in C]

dn, do, dr = digest(new), digest(old), digest(ref)
print("golden_sha256_new_woodbury =", dn)
print("golden_sha256_old_nsolves  =", do)
print("golden_sha256_networkx     =", dr)
print("ISOMORPHISM (old==new==nx):", "PASS" if dn == do == dr else "FAIL")
# raw max abs error new vs old (pre-rounding)
me = 0.0
for a, b in zip(new, old):
    me = max(me, max(0 if (math.isnan(a[k]) and math.isnan(b[k])) else abs(a[k]-b[k]) for k in a))
print(f"raw max|new-old| = {me:.3e}")
