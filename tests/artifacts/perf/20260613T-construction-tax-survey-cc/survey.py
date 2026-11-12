"""Construction-tax survey (cc, 2026-06-13, HEAD-synced env).

Isolates the remaining vs-nx construction gap to MultiGraph attributed
add_edges_from. All other construction paths are at parity or faster.
Run: python3 survey.py
"""
import time, warnings, random
import networkx as nx, franken_networkx as fnx
warnings.filterwarnings("ignore")


def best(f, reps=8):
    b = 1e9
    for _ in range(reps):
        s = time.perf_counter(); f(); b = min(b, time.perf_counter() - s)
    return b * 1e3


def main():
    random.seed(2)
    N = 2000
    E = [(random.randrange(N), random.randrange(N)) for _ in range(8000)]
    EA = [(u, v, {"weight": 1.0}) for u, v in E]

    rows = []

    def bench(name, fcls, ncls, edges):
        tf = best(lambda: (lambda g: g.add_edges_from(edges))(fcls()))
        tn = best(lambda: (lambda g: g.add_edges_from(edges))(ncls()))
        rows.append((name, tf, tn, tn / tf))

    bench("Graph plain", fnx.Graph, nx.Graph, E)
    bench("Graph attributed", fnx.Graph, nx.Graph, EA)
    bench("DiGraph plain", fnx.DiGraph, nx.DiGraph, E)
    bench("DiGraph attributed", fnx.DiGraph, nx.DiGraph, EA)
    bench("MultiGraph plain", fnx.MultiGraph, nx.MultiGraph, E)
    bench("MultiGraph attributed", fnx.MultiGraph, nx.MultiGraph, EA)
    bench("MultiDiGraph plain", fnx.MultiDiGraph, nx.MultiDiGraph, E)
    bench("MultiDiGraph attributed", fnx.MultiDiGraph, nx.MultiDiGraph, EA)

    # add_nodes_from / copy
    NODES = list(range(20000))
    rows.append(("add_nodes_from(20k)",
                 best(lambda: fnx.Graph().add_nodes_from(NODES)),
                 best(lambda: nx.Graph().add_nodes_from(NODES)), None))
    gf = fnx.Graph(); gf.add_edges_from(E); gn = nx.Graph(); gn.add_edges_from(E)
    rows.append(("copy", best(gf.copy), best(gn.copy), None))

    print(f"{'op':28s} {'fnx(ms)':>9s} {'nx(ms)':>9s} {'ratio':>7s}")
    for name, tf, tn, r in rows:
        rr = f"{tn/tf:.2f}x" if r is None else f"{r:.2f}x"
        flag = ""
        if tn / tf < 0.8:
            flag = "  <<< SLOWER"
        print(f"{name:28s} {tf:9.2f} {tn:9.2f} {rr:>7s}{flag}")


if __name__ == "__main__":
    main()
