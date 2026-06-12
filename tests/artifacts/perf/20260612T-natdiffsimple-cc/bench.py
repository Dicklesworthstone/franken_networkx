"""Warm min-of-N benchmark for difference (fnx vs nx). Run with PYTHONPATH=repo/python."""
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
    gf = fnx.Graph(gx); hf = fnx.Graph(hx)
    tnx = tm(lambda: nx.difference(gx, hx))
    tfx = tm(lambda: fnx.difference(gf, hf))
    print(f"{name:28s} nx={tnx:8.3f}ms  fnx={tfx:8.3f}ms  ratio={tfx/tnx:5.2f}  (self {tnx/tfx:.2f}x)")


# the original sweep shape (difference(g,g) self -> empty result)
g = nx.barabasi_albert_graph(800, 4, seed=1)
case("BA800 self (empty)", g, g)
# G minus sparser H, real residual
h = nx.gnp_random_graph(800, 0.005, seed=5); h.add_nodes_from(g.nodes())
case("BA800 minus gnp", g, h)
# larger
g2 = nx.barabasi_albert_graph(3000, 5, seed=1)
case("BA3000 self (empty)", g2, g2)
gw = nx.watts_strogatz_graph(2000, 8, 0.2, seed=1)
hw = nx.watts_strogatz_graph(2000, 4, 0.2, seed=2); hw.add_nodes_from(gw.nodes()); gw.add_nodes_from(hw.nodes())
case("WS2000 minus WS", gw, hw)
