import cProfile, pstats, io, time
import networkx as nx, franken_networkx as fnx


def t(f, *a, **k):
    best = 1e9
    for _ in range(5):
        s = time.perf_counter()
        f(*a, **k)
        best = min(best, time.perf_counter() - s)
    return best


for mn in (30, 60, 120):
    r = t(fnx.grid_2d_graph, mn, mn) / t(nx.grid_2d_graph, mn, mn)
    print(f"grid_2d {mn}x{mn}: {r:.2f}x")
r = t(fnx.grid_2d_graph, 60, 60, periodic=True) / t(nx.grid_2d_graph, 60, 60, periodic=True)
print(f"grid_2d 60x60 periodic: {r:.2f}x")

pr = cProfile.Profile()
pr.enable()
fnx.grid_2d_graph(120, 120)
pr.disable()
s = io.StringIO()
pstats.Stats(pr, stream=s).sort_stats("cumulative").print_stats(12)
print(s.getvalue())
