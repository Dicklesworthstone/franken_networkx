import time, hashlib, json, sys, random
import networkx as nx, franken_networkx as fnx

def build(Gn, cls):
    Gf = cls()
    Gf.add_nodes_from(list(Gn))
    if Gn.is_multigraph():
        Gf.add_edges_from([(u, v, k, d) for u, v, k, d in Gn.edges(keys=True, data=True)])
    else:
        Gf.add_edges_from([(u, v, d) for u, v, d in Gn.edges(data=True)])
    return Gf

def corpus():
    random.seed(11)
    out = []
    specs = [
        ("ws", nx.connected_watts_strogatz_graph(150, 6, 0.1, seed=1), nx.Graph, fnx.Graph),
        ("ba", nx.barabasi_albert_graph(150, 3, seed=2), nx.Graph, fnx.Graph),
        ("geo", nx.random_geometric_graph(120, 0.22, seed=3), nx.Graph, fnx.Graph),
    ]
    for name, g, ncls, fcls in specs:
        if not nx.is_connected(g):
            continue
        for u, v in g.edges():
            g[u][v]['weight'] = round(random.uniform(1, 10), 4)
        out.append((name, g, fcls))
    # directed strongly-connected (cycle + chords)
    dg = nx.DiGraph()
    n = 120
    for i in range(n):
        dg.add_edge(i, (i + 1) % n, weight=round(random.uniform(1, 5), 4))
    for i in range(0, n, 7):
        dg.add_edge(i, (i + 3) % n, weight=round(random.uniform(1, 5), 4))
    out.append(("dicyc", dg, fnx.DiGraph))
    # multigraph (parallel edges, min-weight semantics)
    mg = nx.MultiGraph()
    base = nx.connected_watts_strogatz_graph(80, 4, 0.1, seed=5)
    for u, v in base.edges():
        mg.add_edge(u, v, weight=round(random.uniform(3, 9), 4))
        mg.add_edge(u, v, weight=round(random.uniform(1, 3), 4))  # cheaper parallel
    out.append(("multi", mg, fnx.MultiGraph))
    # unweighted multigraph (weight=None path)
    out.append(("multi_unw", mg, fnx.MultiGraph))
    return out

def golden():
    recs = []
    for name, g, fcls in corpus():
        Gf = build(g, fcls)
        wparam = None if name.endswith("_unw") else "weight"
        vn = nx.wiener_index(g, weight=wparam)
        vf = fnx.wiener_index(Gf, weight=wparam)
        # exact bit-pattern compare for floats; equal for ints/inf
        if repr(vn) != repr(vf):
            print(f"MISMATCH {name}: nx={vn!r} fnx={vf!r}")
            return None
        recs.append(f"{name}|{wparam}|{vf!r}|{type(vf).__name__}")
    return hashlib.sha256("\n".join(recs).encode()).hexdigest()

def bench():
    random.seed(2)
    G = nx.connected_watts_strogatz_graph(300, 6, 0.1, seed=4)
    for u, v in G.edges():
        G[u][v]['weight'] = random.uniform(1, 10)
    Gf = fnx.Graph(); Gf.add_nodes_from(list(G)); Gf.add_edges_from([(u, v, d) for u, v, d in G.edges(data=True)])
    def b(fn, *a, **k):
        for _ in range(2): fn(*a, **k)
        ts = []
        for _ in range(7):
            t = time.perf_counter(); fn(*a, **k); ts.append(time.perf_counter() - t)
        return min(ts)
    tn = b(nx.wiener_index, G, weight='weight')
    tf = b(fnx.wiener_index, Gf, weight='weight')
    return {"weighted_n300": {"nx_ms": tn*1000, "fnx_ms": tf*1000, "ratio": tf/tn}}

if __name__ == "__main__":
    sha = golden()
    if sha is None: sys.exit(1)
    print("GOLDEN_SHA=" + sha)
    print(json.dumps(bench(), indent=2))
