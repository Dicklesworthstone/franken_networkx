import time, hashlib, json, sys, random
import networkx as nx, franken_networkx as fnx

def build(g):
    gf = fnx.Graph(); gf.add_nodes_from(g.nodes()); gf.add_edges_from(list(g.edges()))
    return gf

def corpus():
    rnd = random.Random(41)
    out = []
    for t in range(60):
        n = rnd.randint(3, 45)
        out.append(nx.gnm_random_graph(n, rnd.randint(0, int(n * 1.3)), seed=t))
    for t in range(20):
        n = rnd.randint(10, 40)
        g = nx.random_labeled_tree(n, seed=t)
        for _ in range(n // 8):
            u, v = rnd.sample(range(n), 2); g.add_edge(u, v)
        out.append(g)
    out += [nx.path_graph(5), nx.cycle_graph(6), nx.complete_graph(5),
            nx.Graph([(0, 1), (1, 2), (2, 0), (2, 3), (3, 4), (4, 5), (5, 3)])]
    return out

def golden():
    recs = []
    for i, g in enumerate(corpus()):
        gf = build(g)
        try:
            na = sorted(tuple(sorted(e)) for e in nx.k_edge_augmentation(g, 2))
        except Exception as e:
            try:
                fnx.k_edge_augmentation(gf, 2)
                print(f"nx raised {type(e).__name__} fnx didn't (i={i})"); return None
            except Exception as ef:
                if type(ef).__name__ != type(e).__name__:
                    print(f"err mismatch {type(e).__name__} vs {type(ef).__name__}"); return None
                recs.append(f"{i}|ERR"); continue
        fa = sorted(tuple(sorted(e)) for e in fnx.k_edge_augmentation(gf, 2))
        if fa != na:
            print(f"MISMATCH i={i}: fnx={fa[:4]} nx={na[:4]}"); return None
        # validity: G + aug is 2-edge-connected (when augmentation non-empty needs >=3 nodes)
        if fa and g.number_of_nodes() >= 3:
            H = g.copy(); H.add_edges_from(fa)
            if not nx.is_k_edge_connected(H, 2):
                print(f"INVALID i={i}"); return None
        recs.append(f"{i}|{fa!r}")
    return hashlib.sha256("\n".join(recs).encode()).hexdigest()

def bench():
    res = {}
    for n in [100, 400]:
        g = nx.random_labeled_tree(n, seed=4)
        rnd = random.Random(4)
        for _ in range(n // 10):
            u, v = rnd.sample(range(n), 2); g.add_edge(u, v)
        gf = build(g)
        def tm(f, k=6):
            f(); x = time.perf_counter()
            for _ in range(k): f()
            return (time.perf_counter() - x) / k * 1000
        tn = tm(lambda: list(nx.k_edge_augmentation(g, 2)))
        tf = tm(lambda: fnx.k_edge_augmentation(gf, 2))
        res[f"n{n}"] = {"nx_ms": tn, "fnx_ms": tf, "ratio": tf / tn,
                        "n_edges": len(list(nx.k_edge_augmentation(g, 2)))}
    return res

if __name__ == "__main__":
    sha = golden()
    if sha is None: sys.exit(1)
    print("KEAUG_GOLDEN_SHA=" + sha)
    print(json.dumps(bench(), indent=2))
