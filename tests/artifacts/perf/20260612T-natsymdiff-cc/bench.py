"""Warm min-of-N bench for symmetric_difference. Run with PYTHONPATH=repo/python."""
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
    if gx.is_directed():
        gf = fnx.DiGraph(gx); hf = fnx.DiGraph(hx)
    else:
        gf = fnx.Graph(gx); hf = fnx.Graph(hx)
    tnx = tm(lambda: nx.symmetric_difference(gx, hx))
    tfx = tm(lambda: fnx.symmetric_difference(gf, hf))
    print(f"{name:24s} nx={tnx:8.3f}ms  fnx={tfx:8.3f}ms  ratio={tfx/tnx:5.2f}  (self {tnx/tfx:.2f}x vs nx)")


gu = nx.barabasi_albert_graph(800, 4, seed=1); hu = nx.gnp_random_graph(800, 0.01, seed=5)
gu.add_nodes_from(hu.nodes()); hu.add_nodes_from(gu.nodes())
case("u_BA800 sym gnp", gu, hu)
gu2 = nx.watts_strogatz_graph(2000, 8, 0.2, seed=1); hu2 = nx.watts_strogatz_graph(2000, 4, 0.2, seed=2)
gu2.add_nodes_from(hu2.nodes()); hu2.add_nodes_from(gu2.nodes())
case("u_WS2000 sym WS", gu2, hu2)
dg = nx.gnp_random_graph(800, 0.02, seed=1, directed=True); dh = nx.gnp_random_graph(800, 0.01, seed=2, directed=True)
dg.add_nodes_from(dh.nodes()); dh.add_nodes_from(dg.nodes())
case("d_gnp800 sym gnp", dg, dh)
dg2 = nx.gnp_random_graph(2000, 0.01, seed=1, directed=True); dh2 = nx.gnp_random_graph(2000, 0.006, seed=2, directed=True)
dg2.add_nodes_from(dh2.nodes()); dh2.add_nodes_from(dg2.nodes())
case("d_gnp2000 sym gnp", dg2, dh2)
