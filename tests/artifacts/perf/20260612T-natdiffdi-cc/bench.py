"""Warm min-of-N benchmark for directed difference. Run with PYTHONPATH=repo/python."""
import time, warnings
warnings.filterwarnings("ignore")
import networkx as nx
import franken_networkx as fnx


def tm(f, r=11):
    ts = []
    for _ in range(r):
        t0 = time.perf_counter(); f(); ts.append(time.perf_counter() - t0)
    return min(ts) * 1e3


def case(name, gx, hx):
    gf = fnx.DiGraph(gx); hf = fnx.DiGraph(hx)
    tnx = tm(lambda: nx.difference(gx, hx))
    tfx = tm(lambda: fnx.difference(gf, hf))
    print(f"{name:26s} nx={tnx:8.3f}ms  fnx={tfx:8.3f}ms  ratio={tfx/tnx:5.2f}  (self {tnx/tfx:.2f}x vs nx)")


dg = nx.gnp_random_graph(800, 0.02, seed=1, directed=True)
dh = nx.gnp_random_graph(800, 0.01, seed=2, directed=True)
dg.add_nodes_from(dh.nodes()); dh.add_nodes_from(dg.nodes())
case("gnp800 minus gnp", dg, dh)
case("gnp800 self (empty)", dg, dg.copy())
dg2 = nx.gnp_random_graph(2000, 0.01, seed=1, directed=True)
dh2 = nx.gnp_random_graph(2000, 0.005, seed=2, directed=True)
dg2.add_nodes_from(dh2.nodes()); dh2.add_nodes_from(dg2.nodes())
case("gnp2000 minus gnp", dg2, dh2)
case("gnp2000 self (empty)", dg2, dg2.copy())
