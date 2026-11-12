import time, hashlib, json, sys, random
import networkx as nx, franken_networkx as fnx

def mk(n, p, seed, ndemand):
    rnd = random.Random(seed)
    DG = nx.gnp_random_graph(n, p, seed=seed, directed=True)
    for u, v in DG.edges():
        DG[u][v]['capacity'] = rnd.randint(5, 30)
        DG[u][v]['weight'] = rnd.randint(1, 9)
    nodes = list(DG.nodes()); rnd.shuffle(nodes)
    half = ndemand
    for s in nodes[:half]: DG.nodes[s]['demand'] = -10
    for d in nodes[half:2 * half]: DG.nodes[d]['demand'] = 10
    Df = fnx.DiGraph(); Df.add_nodes_from(DG.nodes(data=True))
    Df.add_edges_from([(u, v, d) for u, v, d in DG.edges(data=True)])
    return DG, Df

def corpus():
    specs = [(80, 0.06, 1, 3), (150, 0.05, 2, 4), (200, 0.04, 3, 5),
             (120, 0.08, 4, 6), (60, 0.1, 5, 2)]
    return specs

def golden():
    recs = []
    for n, p, seed, nd in corpus():
        DG, Df = mk(n, p, seed, nd)
        # cost parity (the unique optimum)
        cn = nx.min_cost_flow_cost(DG)
        cf = fnx.min_cost_flow_cost(Df)
        if cn != cf:
            print(f"COST MISMATCH n={n}: nx={cn} fnx={cf}"); return None
        # total flow balance must match (conformance contract)
        ff = fnx.min_cost_flow(Df)
        nf = nx.min_cost_flow(DG)
        tf = sum(sum(inner.values()) for inner in ff.values())
        tn = sum(sum(inner.values()) for inner in nf.values())
        if tf != tn:
            print(f"TOTAL FLOW MISMATCH n={n}: nx={tn} fnx={tf}"); return None
        # fnx flow must be a VALID min-cost flow: cost_of_flow(fnx) == optimal
        if fnx.cost_of_flow(Df, ff) != cn:
            print(f"FNX FLOW NOT OPTIMAL n={n}"); return None
        # network_simplex cost parity
        nscf, _ = fnx.network_simplex(Df)
        if nscf != cn:
            print(f"NS COST MISMATCH n={n}: {nscf} vs {cn}"); return None
        recs.append(f"{n}|{cf}|{tf}")
    return hashlib.sha256("\n".join(recs).encode()).hexdigest()

def bench():
    res = {}
    for n, p in [(300, 0.04), (600, 0.025)]:
        DG, Df = mk(n, p, 4, 5)
        def t(fn, G):
            fn(G)
            s = time.perf_counter()
            for _ in range(3): fn(G)
            return (time.perf_counter() - s) / 3 * 1000
        tn = t(lambda G: nx.min_cost_flow_cost(G), DG)
        tf = t(lambda G: fnx.min_cost_flow_cost(Df), Df)
        res[f"n{n}"] = {"nx_ms": tn, "fnx_ms": tf, "ratio": tf / tn}
    return res

if __name__ == "__main__":
    sha = golden()
    if sha is None: sys.exit(1)
    print("MCF_GOLDEN_SHA=" + sha)
    print(json.dumps(bench(), indent=2))
