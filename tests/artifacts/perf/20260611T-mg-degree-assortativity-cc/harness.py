import time, hashlib, json, sys, random, warnings
import networkx as nx, franken_networkx as fnx
warnings.filterwarnings('ignore')

def build(Gn):
    cls = fnx.MultiDiGraph if Gn.is_directed() else fnx.MultiGraph
    Gf = cls(); Gf.add_nodes_from(list(Gn))
    Gf.add_edges_from([(u, v, k, d) for u, v, k, d in Gn.edges(keys=True, data=True)])
    return Gf

def corpus():
    random.seed(17)
    out = []
    # undirected variants
    b = nx.connected_watts_strogatz_graph(180, 6, 0.15, seed=1)
    g = nx.MultiGraph(); g.add_nodes_from(b.nodes())
    for u, v in b.edges():
        g.add_edge(u, v, weight=round(random.uniform(1, 9), 3))
        if random.random() < 0.4: g.add_edge(u, v, weight=round(random.uniform(1, 9), 3))
    out.append(("undir", g))
    g2 = nx.MultiGraph(g)
    for u in list(g2)[:8]: g2.add_edge(u, u)
    out.append(("undir_selfloop", g2))
    # directed
    db = nx.gnp_random_graph(150, 0.05, seed=2, directed=True)
    dg = nx.MultiDiGraph(); dg.add_nodes_from(db.nodes())
    for u, v in db.edges():
        dg.add_edge(u, v, weight=round(random.uniform(1, 9), 3))
        if random.random() < 0.3: dg.add_edge(u, v, weight=round(random.uniform(1, 9), 3))
    out.append(("dir", dg))
    dg2 = nx.MultiDiGraph(dg)
    for u in list(dg2)[:6]: dg2.add_edge(u, u)
    out.append(("dir_selfloop", dg2))
    # degenerate
    e = nx.MultiGraph(); e.add_nodes_from(range(4)); out.append(("empty", e))
    out.append(("cycle", nx.MultiGraph(nx.cycle_graph(8))))
    p = nx.MultiGraph(); p.add_edge(0, 1); p.add_edge(0, 1); p.add_edge(1, 2); out.append(("parallel", p))
    return out

def golden():
    recs = []
    for name, g in corpus():
        Gf = build(g)
        for wp in (None, "weight"):
            vn = nx.degree_assortativity_coefficient(g, weight=wp)
            vf = fnx.degree_assortativity_coefficient(Gf, weight=wp)
            if repr(vn) != repr(vf):
                print(f"MISMATCH {name} weight={wp}: nx={vn!r} fnx={vf!r}")
                return None
            recs.append(f"{name}|{wp}|{vf!r}")
    return hashlib.sha256("\n".join(recs).encode()).hexdigest()

def bench():
    random.seed(3)
    b = nx.connected_watts_strogatz_graph(200, 6, 0.15, seed=1)
    g = nx.MultiGraph(); g.add_nodes_from(b.nodes())
    for u, v in b.edges():
        g.add_edge(u, v)
        if random.random() < 0.4: g.add_edge(u, v)
    Gf = build(g)
    def t(fn, G):
        for _ in range(2): fn(G)
        ts = []
        for _ in range(20):
            s = time.perf_counter(); fn(G); ts.append(time.perf_counter() - s)
        return min(ts)
    tn = t(lambda G: nx.degree_assortativity_coefficient(G), g)
    tf = t(lambda G: fnx.degree_assortativity_coefficient(G), Gf)
    return {"mg_undir_n200": {"nx_ms": tn*1000, "fnx_ms": tf*1000, "ratio": tf/tn}}

if __name__ == "__main__":
    sha = golden()
    if sha is None: sys.exit(1)
    print("GOLDEN_SHA=" + sha)
    print(json.dumps(bench(), indent=2))
