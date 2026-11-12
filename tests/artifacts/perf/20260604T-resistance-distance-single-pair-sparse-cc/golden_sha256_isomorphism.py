import sys, hashlib, json, random
sys.path.insert(0, "/data/projects/franken_networkx/python")
import numpy as np, networkx as nx, importlib
fnx = importlib.import_module("franken_networkx")
import franken_networkx as F
np.seterr(all="ignore")


def cp(Gx):
    Gf = fnx.Graph(); Gf.add_nodes_from(Gx.nodes()); Gf.add_edges_from(Gx.edges(data=True)); return Gf


def corpus():
    out = []
    for seed in range(20):
        rnd = random.Random(2000 + seed)
        Gx = nx.connected_watts_strogatz_graph(rnd.randint(6, 50), 4, 0.35, seed=seed)
        if seed % 2 == 0:
            for u, v in Gx.edges():
                Gx[u][v]["weight"] = round(rnd.uniform(0.5, 5.0), 4)
        wk = "weight" if seed % 2 == 0 else None
        pairs = [(rnd.randrange(len(Gx)), rnd.randrange(len(Gx))) for _ in range(8)]
        out.append((Gx, cp(Gx), wk, list(Gx.nodes()), pairs))
    return out


def digest(getval, C):
    h = hashlib.sha256()
    for Gx, Gf, wk, nl, pairs in C:
        for ia, ib in pairs:
            r = getval(Gx, Gf, wk, nl[ia], nl[ib])
            h.update(json.dumps(round(r, 8)).encode())
    return h.hexdigest()


C = corpus()
orig = F._resistance_single_pair_sparse

F._resistance_single_pair_sparse = orig
d_sparse = digest(lambda Gx, Gf, wk, a, b: fnx.resistance_distance(Gf, a, b, weight=wk), C)
F._resistance_single_pair_sparse = lambda *a, **k: None
d_dense = digest(lambda Gx, Gf, wk, a, b: fnx.resistance_distance(Gf, a, b, weight=wk), C)
F._resistance_single_pair_sparse = orig
d_nx = digest(lambda Gx, Gf, wk, a, b: nx.resistance_distance(Gx, a, b, weight=wk), C)

print("golden_sha256_sparse_solve =", d_sparse)
print("golden_sha256_dense_pinv   =", d_dense)
print("golden_sha256_networkx     =", d_nx)
print("ISOMORPHISM (sparse==dense==nx):", "PASS" if d_sparse == d_dense == d_nx else "FAIL")
