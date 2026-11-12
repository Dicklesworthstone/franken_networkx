import hashlib, random
import networkx as nx, franken_networkx as fnx
from franken_networkx.backend import _fnx_to_nx

def fingerprint(G):
    parts = []
    parts.append("NODES:" + "|".join(f"{n!r}={sorted(d.items())!r}" for n, d in G.nodes(data=True)))
    parts.append("EDGES:" + "|".join(
        f"{u!r}-{v!r}-{k!r}={sorted(dd.items())!r}" for u, v, k, dd in G.edges(keys=True, data=True)
    ))
    parts.append("SUCC:" + "|".join(f"{n!r}:{[repr(x) for x in G._succ[n]]}" for n in G))
    parts.append("PRED:" + "|".join(f"{n!r}:{[repr(x) for x in G._pred[n]]}" for n in G))
    parts.append("GRAPH:" + repr(sorted(G.graph.items())))
    return hashlib.sha256("\n".join(parts).encode()).hexdigest()

def corpus():
    rnd = random.Random(41)
    out = []
    db = nx.gnp_random_graph(140, 0.04, seed=2, directed=True)
    g = fnx.MultiDiGraph(); g.graph["k"] = "v"
    for u, v in db.edges():
        g.add_edge(u, v, w=round(rnd.random(), 4))
        if rnd.random() < 0.3: g.add_edge(u, v, c="r")
    out.append(g)
    # self loops + antiparallel + isolated
    g2 = fnx.MultiDiGraph()
    for u, v, k, d in _fnx_to_nx(g).edges(keys=True, data=True):
        g2.add_edge(u, v, key=k, **d)
    for u in list(g2)[:6]:
        g2.add_edge(u, u); g2.add_edge(u, (u + 1) % 100)
    g2.add_nodes_from([7771, 7772])
    out.append(g2)
    # string nodes
    g3 = fnx.MultiDiGraph()
    for a in "abcde":
        for b in "abcde":
            if a != b:
                for _ in range(rnd.randrange(1, 3)):
                    g3.add_edge(a, b, w=rnd.randrange(9))
    out.append(g3)
    # random corpus with shuffled insertion order (stresses pred order)
    for t in range(8):
        gg = fnx.MultiDiGraph()
        edges = [(rnd.randrange(18), rnd.randrange(18)) for _ in range(rnd.randrange(5, 70))]
        for u, v in edges:
            gg.add_edge(u, v, w=u)
        out.append(gg)
    return out

def run():
    recs = [f"{i}|{fingerprint(_fnx_to_nx(g))}" for i, g in enumerate(corpus())]
    return hashlib.sha256("\n".join(recs).encode()).hexdigest()

if __name__ == "__main__":
    print("DIR_CONV_SHA=" + run())
