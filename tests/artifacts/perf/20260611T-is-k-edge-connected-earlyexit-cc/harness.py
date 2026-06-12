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
        out.append(nx.gnm_random_graph(n, rnd.randint(0, n * 2), seed=t))
    out += [nx.complete_graph(6), nx.cycle_graph(10), nx.path_graph(8),
            nx.petersen_graph(), nx.icosahedral_graph(), nx.empty_graph(5),
            nx.star_graph(7)]
    return out

def golden():
    recs = []
    for i, g in enumerate(corpus()):
        gf = build(g)
        for k in [1, 2, 3, 4, 5]:
            try:
                nr = nx.is_k_edge_connected(g, k)
            except Exception as e:
                try:
                    fnx.is_k_edge_connected(gf, k)
                    print(f"nx raised {type(e).__name__} fnx didn't (i={i} k={k})"); return None
                except Exception as ef:
                    if type(ef).__name__ != type(e).__name__:
                        print(f"err mismatch {type(e).__name__} vs {type(ef).__name__}"); return None
                    recs.append(f"{i}|{k}|ERR"); continue
            fr = fnx.is_k_edge_connected(gf, k)
            if fr != nr:
                print(f"MISMATCH i={i} k={k}: nx={nr} fnx={fr}"); return None
            recs.append(f"{i}|{k}|{int(fr)}")
    return hashlib.sha256("\n".join(recs).encode()).hexdigest()

def bench():
    res = {}
    for n in [400, 1000]:
        g = nx.connected_watts_strogatz_graph(n, 8, 0.1, seed=4)
        gf = build(g)
        for k in [2, 3]:
            def tm(f, kk=8):
                f(); x = time.perf_counter()
                for _ in range(kk): f()
                return (time.perf_counter() - x) / kk * 1000
            tn = tm(lambda: nx.is_k_edge_connected(g, k))
            tf = tm(lambda: fnx.is_k_edge_connected(gf, k))
            res[f"n{n}_k{k}"] = {"nx_ms": tn, "fnx_ms": tf, "ratio": tf / tn}
    return res

if __name__ == "__main__":
    sha = golden()
    if sha is None: sys.exit(1)
    print("IKEC_GOLDEN_SHA=" + sha)
    print(json.dumps(bench(), indent=2))
