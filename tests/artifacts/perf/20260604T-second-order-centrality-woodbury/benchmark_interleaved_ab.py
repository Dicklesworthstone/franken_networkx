import sys, time, random
sys.path.insert(0, "/data/projects/franken_networkx/python")
import numpy as np
import networkx as nx
import importlib
fnx = importlib.import_module("franken_networkx")
import franken_networkx as F
np.seterr(all="ignore")


def cp(Gx):
    Gf = fnx.Graph(); Gf.add_nodes_from(Gx.nodes()); Gf.add_edges_from(Gx.edges(data=True)); return Gf


def w(n, seed):
    Gx = nx.connected_watts_strogatz_graph(n, 6, 0.3, seed=seed)
    rnd = random.Random(seed)
    for u, v in Gx.edges():
        Gx[u][v]["weight"] = rnd.uniform(0.5, 4.0)
    return cp(Gx)


orig = F._second_order_fundamental_columns


def one(Gf, fast):
    F._second_order_fundamental_columns = orig if fast else (lambda *a, **k: None)
    s = time.perf_counter(); fnx.second_order_centrality(Gf, weight="weight"); return time.perf_counter() - s


for n in (60, 100, 140, 180):
    Gf = w(n, 3)
    one(Gf, True)  # warm
    tnew = tnold = float("inf")
    # interleave 5 rounds, take min of each
    for _ in range(5):
        tnew = min(tnew, one(Gf, True))
        tnold = min(tnold, one(Gf, False))
    F._second_order_fundamental_columns = orig
    print(f"n={n:4d}  old={tnold:8.4f}s  new={tnew:7.4f}s  speedup={tnold/tnew:6.1f}x", flush=True)
