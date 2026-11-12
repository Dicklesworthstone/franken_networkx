import time, hashlib, json, sys
import networkx as nx, franken_networkx as fnx

def build(g):
    gf = fnx.Graph(); gf.add_nodes_from(g.nodes()); gf.add_edges_from(list(g.edges()))
    return gf

def corpus():
    out = []
    for n in [30, 50, 80, 100, 120, 150]:
        out.append(nx.connected_watts_strogatz_graph(n, 4, 0.3, seed=n))
    out.append(nx.path_graph(5))
    out.append(nx.cycle_graph(8))
    out.append(nx.karate_club_graph())
    return out

def golden():
    # The lu substitution must produce the SAME result fnx already returns with
    # the full solver (both exactly solve L p = b). Verify fnx-new(lu, default)
    # == fnx-old(full) within machine epsilon for every graph/seed.
    from franken_networkx import _call_networkx_for_parity
    recs = []
    worst = 0.0
    for i, g in enumerate(corpus()):
        gf = build(g)
        for seed in (1, 7, 42):
            old = _call_networkx_for_parity(
                "approximate_current_flow_betweenness_centrality",
                gf, seed=seed, solver="full",
            )
            new = fnx.approximate_current_flow_betweenness_centrality(gf, seed=seed)
            if set(old) != set(new):
                print(f"KEY MISMATCH i={i} seed={seed}"); return None
            md = max((abs(old[k] - new[k]) for k in old), default=0.0)
            worst = max(worst, md)
            if md > 1e-9:
                print(f"VALUE MISMATCH (lu vs full) i={i} seed={seed} maxdiff={md:.3e}"); return None
            recs.append(f"{i}|{seed}|" + "|".join(f"{round(new[k], 10)}" for k in sorted(new, key=repr)))
    print(f"# worst |fnx_lu - fnx_full| = {worst:.3e}")
    return hashlib.sha256("\n".join(recs).encode()).hexdigest()

def bench():
    res = {}
    for n in [200, 400]:
        g = nx.connected_watts_strogatz_graph(n, 6, 0.2, seed=n)
        gf = build(g)
        def tm(f, k=4):
            f(); x = time.perf_counter()
            for _ in range(k): f()
            return (time.perf_counter() - x) / k * 1000
        tn = tm(lambda: nx.approximate_current_flow_betweenness_centrality(g, seed=1))
        tf = tm(lambda: fnx.approximate_current_flow_betweenness_centrality(gf, seed=1))
        res[f"n{n}"] = {"nx_default_ms": tn, "fnx_ms": tf, "ratio": tf / tn}
    return res

if __name__ == "__main__":
    sha = golden()
    if sha is None: sys.exit(1)
    print("ACFB_GOLDEN_SHA=" + sha)
    print(json.dumps(bench(), indent=2))
