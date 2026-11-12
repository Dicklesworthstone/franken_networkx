import time, hashlib, json, sys, random
import networkx as nx, franken_networkx as fnx

def build(Gn):
    Gf = fnx.DiGraph() if Gn.is_directed() else fnx.Graph()
    Gf.add_nodes_from(list(Gn.nodes())); Gf.add_edges_from(list(Gn.edges()))
    return Gf

def corpus():
    out = []
    rnd = random.Random(31)
    for t in range(40):
        n = rnd.randint(6, 60)
        g = nx.gnm_random_graph(n, rnd.randint(n, n * 3), seed=t)
        if nx.is_connected(g):
            out.append(("u", g))
    for t in range(30):
        n = rnd.randint(6, 45)
        d = nx.gnp_random_graph(n, 0.2, seed=t, directed=True)
        out.append(("d", d))
    # structured
    out.append(("u", nx.icosahedral_graph()))
    out.append(("u", nx.karate_club_graph()))
    out.append(("u", nx.cycle_graph(12)))
    return out

def golden():
    recs = []
    for tag, g in corpus():
        gf = build(g)
        nodes = list(g.nodes())
        # sample a few (s,t) pairs
        pairs = [(nodes[0], nodes[-1]), (nodes[1 % len(nodes)], nodes[len(nodes) // 2])]
        for s, t in pairs:
            if s == t:
                continue
            try:
                nc = nx.minimum_edge_cut(g, s, t)
            except Exception as e:
                fr = None
                try:
                    fnx.minimum_edge_cut(gf, s, t)
                    print(f"nx raised {type(e).__name__} but fnx didn't"); return None
                except Exception as ef:
                    if type(ef).__name__ != type(e).__name__:
                        print(f"err mismatch nx={type(e).__name__} fnx={type(ef).__name__}"); return None
                    recs.append(f"{tag}|{s}|{t}|ERR:{type(e).__name__}")
                    continue
            fc = fnx.minimum_edge_cut(gf, s, t)
            if fc != nc:
                print(f"MISMATCH {tag} s={s} t={t}: fnx={sorted(fc)[:5]} nx={sorted(nc)[:5]}")
                return None
            recs.append(f"{tag}|{s}|{t}|{sorted(fc)!r}")
    return hashlib.sha256("\n".join(recs).encode()).hexdigest()

def bench():
    res = {}
    for n in [800, 2000]:
        g = nx.connected_watts_strogatz_graph(n, 8, 0.1, seed=4)
        gf = build(g)
        s, t = 0, n // 2
        def tm(f, k=8):
            f(); x = time.perf_counter()
            for _ in range(k): f()
            return (time.perf_counter() - x) / k * 1000
        tn = tm(lambda: nx.minimum_edge_cut(g, s, t))
        tf = tm(lambda: fnx.minimum_edge_cut(gf, s, t))
        res[f"n{n}"] = {"nx_ms": tn, "fnx_ms": tf, "ratio": tf / tn}
    return res

if __name__ == "__main__":
    sha = golden()
    if sha is None: sys.exit(1)
    print("MINCUT_GOLDEN_SHA=" + sha)
    print(json.dumps(bench(), indent=2))
