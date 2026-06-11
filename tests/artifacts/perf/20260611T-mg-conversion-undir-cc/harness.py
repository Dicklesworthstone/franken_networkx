import hashlib, json, sys, random
import networkx as nx, franken_networkx as fnx
from franken_networkx.backend import _fnx_to_nx

def graph_fingerprint(G):
    """Deterministic structural fingerprint of an nx (multi)graph: node order
    + node data, edge (u,v,key,data) order, adjacency row neighbour order, and
    graph attrs. Captures everything a delegated algorithm could observe."""
    parts = []
    parts.append("NODES:" + "|".join(f"{n!r}={sorted(d.items())!r}" for n, d in G.nodes(data=True)))
    parts.append("EDGES:" + "|".join(
        f"{u!r}-{v!r}-{k!r}={sorted(dd.items())!r}" for u, v, k, dd in G.edges(keys=True, data=True)
    ))
    parts.append("ADJ:" + "|".join(f"{n!r}:{[repr(x) for x in G.adj[n]]}" for n in G))
    parts.append("GRAPH:" + repr(sorted(G.graph.items())))
    return hashlib.sha256("\n".join(parts).encode()).hexdigest()

def corpus():
    rnd = random.Random(31)
    out = []
    # varied undirected multigraphs (parallel edges, weights, self-loops, string/mixed nodes)
    b = nx.connected_watts_strogatz_graph(150, 6, 0.2, seed=1)
    g = fnx.MultiGraph(); g.graph["name"] = "ws"
    for u, v in b.edges():
        g.add_edge(u, v, weight=round(rnd.random(), 4))
        if rnd.random() < 0.4: g.add_edge(u, v, color="r")
    out.append(g)
    # self loops + isolated
    g2 = fnx.MultiGraph()
    for u, v, k, d in _fnx_to_nx(g).edges(keys=True, data=True):
        g2.add_edge(u, v, key=k, **d)
    for u in list(g2)[:6]: g2.add_edge(u, u, loop=1)
    g2.add_nodes_from([9991, 9992])
    out.append(g2)
    # string nodes, dense parallels
    g3 = fnx.MultiGraph()
    for a in "abcdef":
        for bb in "abcdef":
            if a < bb:
                for _ in range(rnd.randrange(1, 4)):
                    g3.add_edge(a, bb, w=rnd.randrange(10))
    out.append(g3)
    # random small corpus
    for t in range(8):
        gg = fnx.MultiGraph()
        for _ in range(rnd.randrange(5, 60)):
            u, v = rnd.randrange(20), rnd.randrange(20)
            gg.add_edge(u, v, w=u)
        out.append(gg)
    return out

def run():
    recs = []
    for i, g in enumerate(corpus()):
        recs.append(f"{i}|{graph_fingerprint(_fnx_to_nx(g))}")
    return hashlib.sha256("\n".join(recs).encode()).hexdigest()

if __name__ == "__main__":
    print("CONV_SHA=" + run())
