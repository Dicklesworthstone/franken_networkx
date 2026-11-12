"""Parity + golden proof for native simple-Graph/DiGraph symmetric_difference
(br-r37-c1-natsymdiff / -di). Run with PYTHONPATH=<repo>/python.
"""
import hashlib, json, warnings, sys
warnings.filterwarnings("ignore")
import networkx as nx
import franken_networkx as fnx


def canon(R):
    return {
        "directed": R.is_directed(),
        "multigraph": R.is_multigraph(),
        "nodes": list(R.nodes()),
        "edges": list(R.edges()),
        "graph_attr_keys": sorted(R.graph.keys()),
    }


def make(directed, nodes, edges):
    g = nx.DiGraph() if directed else nx.Graph()
    g.add_nodes_from(nodes); g.add_edges_from(edges); return g


CASES = []
# undirected curated
CASES.append(("u_empty", nx.Graph(), nx.Graph()))
CASES.append(("u_identical", nx.barabasi_albert_graph(50, 3, seed=2), nx.barabasi_albert_graph(50, 3, seed=2)))
CASES.append(("u_selfloops", make(False, [0, 1], [(0, 0), (0, 1), (1, 1)]), make(False, [0, 1], [(0, 1), (1, 1)])))
CASES.append(("u_string", make(False, ["a", "b", "c"], [("a", "b"), ("b", "c")]), make(False, ["a", "b", "c"], [("b", "c"), ("a", "c")])))
gu = nx.barabasi_albert_graph(80, 3, seed=4); hu = nx.gnp_random_graph(80, 0.08, seed=9)
gu.add_nodes_from(hu.nodes()); hu.add_nodes_from(gu.nodes())
CASES.append(("u_BA_sym_gnp", gu, hu))
# attrs dropped
ga = nx.path_graph(10)
for n in ga: ga.nodes[n]["x"] = n
for u, v in ga.edges(): ga.edges[u, v]["w"] = 1.0
ha = nx.path_graph(10); ha.add_edge(0, 5)
CASES.append(("u_attrs", ga, ha))
# graph attrs
gg = nx.cycle_graph(8); gg.graph["name"] = "c8"; hg = nx.cycle_graph(8); hg.add_edge(0, 4)
CASES.append(("u_graphattrs", gg, hg))
# directed curated
CASES.append(("d_empty", nx.DiGraph(), nx.DiGraph()))
CASES.append(("d_orientation", make(True, [0, 1, 2], [(0, 1), (1, 0), (1, 2)]), make(True, [0, 1, 2], [(1, 0), (2, 1)])))
gd = nx.gnp_random_graph(80, 0.05, seed=4, directed=True); hd = nx.gnp_random_graph(80, 0.04, seed=9, directed=True)
gd.add_nodes_from(hd.nodes()); hd.add_nodes_from(gd.nodes())
CASES.append(("d_gnp_sym", gd, hd))
CASES.append(("d_identical", gd, gd.copy()))
# seeded sweeps, both directedness, DIFFERENT node insertion orders for G and H
for seed in range(30):
    n = 6 + (seed % 30)
    for directed in (False, True):
        p = 0.05 + (seed % 5) * 0.05
        a = nx.gnp_random_graph(n, p, seed=seed, directed=directed)
        b = nx.gnp_random_graph(n, p * 0.6, seed=seed + 5000, directed=directed)
        # shuffle H's node insertion order so G-index != H-index
        order = list(range(n)); order = order[::-1]
        b2 = (nx.DiGraph() if directed else nx.Graph()); b2.add_nodes_from(order); b2.add_edges_from(b.edges())
        a.add_nodes_from(b2.nodes()); b2.add_nodes_from(a.nodes())
        CASES.append((f"{'d' if directed else 'u'}_rand_{seed}", a, b2))


def run():
    fails, fps, native_hits = [], [], 0
    for name, gx, hx in CASES:
        if gx.is_directed():
            gf = fnx.DiGraph(gx); hf = fnx.DiGraph(hx)
        else:
            gf = fnx.Graph(gx); hf = fnx.Graph(hx)
        if set(gx) != set(hx):
            fails.append((name, "SETUP unequal sets")); continue
        if gf._native_symmetric_difference(hf) is not None:
            native_hits += 1
        cn = canon(nx.symmetric_difference(gx, hx)); cf = canon(fnx.symmetric_difference(gf, hf))
        if cn != cf:
            fails.append((name, {"nx": cn, "fnx": cf}))
        fps.append((name, cf))
    sha = hashlib.sha256(json.dumps(fps, sort_keys=True, default=str).encode()).hexdigest()
    print(f"cases={len(CASES)} native_hits={native_hits} mismatches={len(fails)}")
    print(f"golden_sha256={sha}")
    if fails:
        for nm, d in fails[:8]:
            print("MISMATCH", nm, str(d)[:400])
        sys.exit(1)
    print("ALL PARITY OK")


if __name__ == "__main__":
    run()
