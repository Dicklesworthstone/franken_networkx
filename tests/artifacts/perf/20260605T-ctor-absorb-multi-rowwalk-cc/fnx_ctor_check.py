import time, random
import networkx as nx, franken_networkx as fnx

rnd = random.Random(1)


def t(f, *a):
    best = 1e9
    for _ in range(5):
        s = time.perf_counter()
        f(*a)
        best = min(best, time.perf_counter() - s)
    return best


for n, m in [(800, 3200), (3000, 12000)]:
    de = [(rnd.randrange(n), rnd.randrange(n)) for _ in range(m)]
    fd, nd = fnx.DiGraph(de), nx.DiGraph(de)
    fg, ng = fnx.Graph(de), nx.Graph(de)
    print(f"n={n} E~{m}:")
    print(f"  DiGraph(DiGraph) : {t(lambda: fnx.DiGraph(fd)) / t(lambda: nx.DiGraph(nd)):.2f}x")
    print(f"  Graph(Graph)     : {t(lambda: fnx.Graph(fg)) / t(lambda: nx.Graph(ng)):.2f}x")
    print(f"  DiGraph(Graph)   : {t(lambda: fnx.DiGraph(fg)) / t(lambda: nx.DiGraph(ng)):.2f}x")
    print(f"  Graph(DiGraph)   : {t(lambda: fnx.Graph(fd)) / t(lambda: nx.Graph(nd)):.2f}x")
