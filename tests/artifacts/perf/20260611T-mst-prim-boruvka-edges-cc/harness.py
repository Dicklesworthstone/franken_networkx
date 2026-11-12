import time, hashlib, json, sys, random
import networkx as nx, franken_networkx as fnx

def pair(edges):
    fg, ng = fnx.Graph(), nx.Graph()
    for u, v, w in edges:
        fg.add_edge(u, v, weight=w); ng.add_edge(u, v, weight=w)
    return fg, ng

def corpus():
    rnd = random.Random(7)
    out = []
    # structured (unique / near-unique MSTs) — these lock exact edge parity
    out.append([(0,1,1),(1,2,2),(2,3,3),(3,0,4),(0,2,5)])
    out.append([(i, i+1, i+1) for i in range(12)] + [(0, 6, 100), (3, 9, 50)])
    # star + cycle
    out.append([(0, i, i) for i in range(1, 10)] + [(1, 2, 1), (3, 4, 2)])
    # random sparse with distinct weights (unique MST)
    for t in range(10):
        g = nx.gnm_random_graph(20 + t, 40 + 2 * t, seed=t)
        if not nx.is_connected(g):
            g = nx.connected_watts_strogatz_graph(20 + t, 4, 0.3, seed=t)
        w = list(range(1, g.number_of_edges() + 1)); rnd.shuffle(w)
        out.append([(u, v, w[i]) for i, (u, v) in enumerate(g.edges())])
    return out

def golden():
    recs = []
    for i, edges in enumerate(corpus()):
        for algo in ("prim", "boruvka"):
            fg, ng = pair(edges)
            ft = fnx.minimum_spanning_tree(fg, algorithm=algo)
            nt = nx.minimum_spanning_tree(ng, algorithm=algo)
            fe = sorted((u, v, d.get("weight")) for u, v, d in ft.edges(data=True))
            ne = sorted((u, v, d.get("weight")) for u, v, d in nt.edges(data=True))
            if fe != ne:
                print(f"EDGE MISMATCH corpus={i} {algo}: fnx={fe[:4]} nx={ne[:4]}")
                return None
            # maximum variant too
            fm = fnx.maximum_spanning_tree(fg, algorithm=algo)
            nm = nx.maximum_spanning_tree(ng, algorithm=algo)
            fme = sorted((u, v, d.get("weight")) for u, v, d in fm.edges(data=True))
            nme = sorted((u, v, d.get("weight")) for u, v, d in nm.edges(data=True))
            if fme != nme:
                print(f"MAX EDGE MISMATCH corpus={i} {algo}"); return None
            recs.append(f"{i}|{algo}|{fe!r}|{fme!r}")
    return hashlib.sha256("\n".join(recs).encode()).hexdigest()

def bench():
    random.seed(4)
    res = {}
    for n, k in [(800, 8), (1500, 10)]:
        UG = nx.connected_watts_strogatz_graph(n, k, 0.1, seed=4)
        for u, v in UG.edges(): UG[u][v]['weight'] = random.randint(1, 20)
        Uf = fnx.Graph(); Uf.add_nodes_from(UG.nodes(data=True))
        Uf.add_edges_from([(u, v, d) for u, v, d in UG.edges(data=True)])
        for algo in ("prim", "boruvka"):
            def t(f):
                f(); s = time.perf_counter()
                for _ in range(8): f()
                return (time.perf_counter() - s) / 8 * 1000
            tn = t(lambda: nx.minimum_spanning_tree(UG, algorithm=algo))
            tf = t(lambda: fnx.minimum_spanning_tree(Uf, algorithm=algo))
            res[f"n{n}_{algo}"] = {"nx_ms": tn, "fnx_ms": tf, "ratio": tf / tn}
    return res

if __name__ == "__main__":
    sha = golden()
    if sha is None: sys.exit(1)
    print("MST_GOLDEN_SHA=" + sha)
    print(json.dumps(bench(), indent=2))
