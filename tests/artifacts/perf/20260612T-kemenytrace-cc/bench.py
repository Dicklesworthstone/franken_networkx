"""Warm interleaved bench for kemeny_constant. nx == old fnx (was verbatim nx).
Run with PYTHONPATH=repo/python."""
import time, warnings
warnings.filterwarnings("ignore")
import networkx as nx
import franken_networkx as fnx


def case(name, gx):
    gf = fnx.Graph(gx)
    tn, tf = [], []
    for _ in range(13):
        t0 = time.perf_counter(); nx.kemeny_constant(gx); tn.append(time.perf_counter() - t0)
        t0 = time.perf_counter(); fnx.kemeny_constant(gf); tf.append(time.perf_counter() - t0)
    tn, tf = min(tn) * 1e3, min(tf) * 1e3
    print(f"{name:14s} n={len(gx):5d} nx/oldfnx={tn:8.3f}ms  fnx={tf:8.3f}ms  ratio={tf/tn:5.2f}  self-speedup={tn/tf:.2f}x")


case("ws150", nx.watts_strogatz_graph(150, 6, 0.3, seed=1))   # below gate -> identical
case("ws300", nx.watts_strogatz_graph(300, 6, 0.3, seed=1))
case("ba500", nx.barabasi_albert_graph(500, 4, seed=1))
case("ba800", nx.barabasi_albert_graph(800, 5, seed=1))
case("ws1000", nx.watts_strogatz_graph(1000, 6, 0.3, seed=2))
case("ba1500", nx.barabasi_albert_graph(1500, 5, seed=1))
