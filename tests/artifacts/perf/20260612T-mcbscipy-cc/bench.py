"""Bench minimum_cycle_basis: scipy-batched de Pina vs nx. PYTHONPATH=repo/python.
nx timing == old fnx (which delegated the whole algorithm to nx)."""
import time, warnings
warnings.filterwarnings("ignore")
import networkx as nx
import franken_networkx as fnx


def tm(f, r=3):
    ts = []
    for _ in range(r):
        t0 = time.perf_counter(); f(); ts.append(time.perf_counter() - t0)
    return min(ts) * 1e3


for name, G in [
    ("ws80", nx.watts_strogatz_graph(80, 6, 0.3, seed=1)),
    ("ws100", nx.watts_strogatz_graph(100, 6, 0.3, seed=1)),
    ("ws120", nx.watts_strogatz_graph(120, 6, 0.3, seed=1)),
    ("ws150", nx.watts_strogatz_graph(150, 6, 0.3, seed=1)),
]:
    gf = fnx.Graph(G)
    tn = tm(lambda: nx.minimum_cycle_basis(G), 2)
    tf = tm(lambda: fnx.minimum_cycle_basis(gf), 2)
    print(f"{name:7s} n={len(G):4d}  nx/oldfnx={tn:9.1f}ms  fnx={tf:8.1f}ms  speedup={tn/tf:.1f}x")
