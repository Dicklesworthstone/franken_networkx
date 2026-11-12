import time, hashlib, json, sys
import networkx as nx
import franken_networkx as fnx

def build(Gn):
    Gf = fnx.DiGraph()
    Gf.add_nodes_from(list(Gn.nodes())); Gf.add_edges_from(list(Gn.edges()))
    return Gf

def dags():
    gs = []
    gs.append(nx.gn_graph(300, seed=3))                       # tree-DAG
    g = nx.gnp_random_graph(120, 0.05, seed=5, directed=True) # random -> DAG by orienting low->high
    dag = nx.DiGraph((u, v) for u, v in g.edges() if u < v); dag.add_nodes_from(g.nodes()); gs.append(dag)
    gs.append(nx.random_labeled_tree(200, seed=7).to_directed())  # NOT a dag (cycles) -> skip; handle below
    # a layered DAG (diamonds)
    d = nx.DiGraph()
    for i in range(100):
        d.add_edge(i, i+1); d.add_edge(i, i+2 if i+2<=101 else i+1)
    gs.append(d)
    # binary-tree style DAG with shared ancestors
    b = nx.DiGraph()
    for i in range(1, 150):
        b.add_edge(i//2, i)
    gs.append(b)
    out = []
    for g in gs:
        if g.is_directed() and nx.is_directed_acyclic_graph(g):
            out.append(g)
    return out

def golden():
    recs = []
    for gi, Gn in enumerate(dags()):
        Gf = build(Gn)
        nodes = list(Gn.nodes())
        m = len(nodes)
        # sample pairs deterministically
        pairs = []
        for a in range(0, m, max(1, m//15)):
            for b in range(0, m, max(1, m//15)):
                pairs.append((nodes[a], nodes[b]))
        # single-pair API
        for (s, t) in pairs:
            rn = nx.lowest_common_ancestor(Gn, s, t, default="NONE")
            rf = fnx.lowest_common_ancestor(Gf, s, t, default="NONE")
            if rn != rf:
                print(f"MISMATCH single g{gi} s={s} t={t} nx={rn} fnx={rf}"); return None
            recs.append(f"{gi}|{s}|{t}|{rf}")
        # all-pairs API on a subset graph (smaller) to keep golden stable
        apn = dict(nx.all_pairs_lowest_common_ancestor(Gn, pairs=pairs))
        apf = dict(fnx.all_pairs_lowest_common_ancestor(Gf, pairs=pairs))
        if apn != apf:
            # report first diff
            for k in apn:
                if apn.get(k) != apf.get(k):
                    print(f"MISMATCH allpairs g{gi} pair={k} nx={apn.get(k)} fnx={apf.get(k)}"); return None
            print(f"MISMATCH allpairs g{gi} keyset differs"); return None
        recs.append(f"ap{gi}|" + "|".join(f"{k}:{v}" for k, v in sorted(apf.items(), key=lambda kv: str(kv[0]))))
    return hashlib.sha256("\n".join(recs).encode()).hexdigest(), len(recs)

def bench():
    N = 2000
    DAG = nx.gn_graph(N, seed=11)
    Df = build(DAG)
    nodes = list(DAG.nodes())
    res = {}
    # single pair (the reported gap)
    s, t = nodes[0], nodes[1500]
    def b(fn):
        for _ in range(3): fn()
        ts = []
        for _ in range(300):
            x = time.perf_counter(); fn(); ts.append(time.perf_counter()-x)
        return min(ts)
    tn = b(lambda: nx.lowest_common_ancestor(DAG, s, t))
    tf = b(lambda: fnx.lowest_common_ancestor(Df, s, t))
    res["single_pair_n2000"] = {"nx_ms": tn*1000, "fnx_ms": tf*1000, "ratio": tf/tn}
    # few pairs (10)
    fp = [(nodes[i], nodes[i+50]) for i in range(0, 500, 50)]
    tn = b(lambda: list(nx.all_pairs_lowest_common_ancestor(DAG, pairs=fp)))
    tf = b(lambda: list(fnx.all_pairs_lowest_common_ancestor(Df, pairs=fp)))
    res["ten_pairs_n2000"] = {"nx_ms": tn*1000, "fnx_ms": tf*1000, "ratio": tf/tn}
    return res

if __name__ == "__main__":
    g = golden()
    if g is None: sys.exit(1)
    sha, nrec = g
    print(f"GOLDEN_SHA={sha} records={nrec}")
    print(json.dumps(bench(), indent=2))
