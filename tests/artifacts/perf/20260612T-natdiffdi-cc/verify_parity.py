"""Parity + golden proof for native simple-DiGraph difference (br-r37-c1-natdiffsimple-di).

Run with PYTHONPATH=<repo>/python. Compares fnx.difference vs nx.difference byte-for-byte
for directed graphs across many shapes, verifies the native path is exercised, emits sha256.
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


CASES = []
CASES.append(("empty_vs_empty", nx.DiGraph(), nx.DiGraph()))
CASES.append(("singleton", nx.DiGraph([(0, 0)]), nx.DiGraph([(0, 0)])))


def dibuild(nodes, edges):
    g = nx.DiGraph(); g.add_nodes_from(nodes); g.add_edges_from(edges); return g


CASES.append(("selfloops_dir", dibuild([0, 1], [(0, 0), (0, 1), (1, 0), (1, 1)]),
              dibuild([0, 1], [(0, 1)])))
# orientation sensitivity: H has (1,0) but not (0,1) -> (0,1) kept, (1,0) removed
CASES.append(("orientation", dibuild([0, 1, 2], [(0, 1), (1, 0), (1, 2), (2, 1)]),
              dibuild([0, 1, 2], [(1, 0), (2, 1)])))
g1 = nx.gnp_random_graph(80, 0.05, seed=4, directed=True)
h1 = nx.gnp_random_graph(80, 0.03, seed=9, directed=True)
g1.add_nodes_from(h1.nodes()); h1.add_nodes_from(g1.nodes())
CASES.append(("gnp_dir", g1, h1))
# identical -> empty
g2 = nx.gnp_random_graph(60, 0.08, seed=2, directed=True)
CASES.append(("identical_empty", g2, g2.copy()))
# string nodes
CASES.append(("string_nodes", dibuild(["a", "b", "c"], [("a", "b"), ("b", "c"), ("c", "a")]),
              dibuild(["a", "b", "c"], [("b", "c")])))
# attrs dropped
g3 = nx.DiGraph(); g3.add_edges_from([(i, i + 1) for i in range(10)])
for n in g3: g3.nodes[n]["x"] = n
for u, v in g3.edges(): g3.edges[u, v]["w"] = 2.0
h3 = nx.DiGraph(); h3.add_edges_from([(i, i + 1) for i in range(0, 10, 2)]); h3.add_nodes_from(g3.nodes())
g3.add_nodes_from(h3.nodes())
CASES.append(("attrs_dropped", g3, h3))
# graph attrs
g4 = nx.cycle_graph(8, create_using=nx.DiGraph); g4.graph["name"] = "c8"
h4 = nx.cycle_graph(8, create_using=nx.DiGraph)
CASES.append(("graph_attrs", g4, h4))
# seeded sweep
for seed in range(40):
    n = 5 + (seed % 40)
    p = 0.04 + (seed % 6) * 0.04
    ga = nx.gnp_random_graph(n, p, seed=seed, directed=True)
    hb = nx.gnp_random_graph(n, 0.5 * p, seed=seed + 7000, directed=True)
    ga.add_nodes_from(hb.nodes()); hb.add_nodes_from(ga.nodes())
    CASES.append((f"rand_{seed}", ga, hb))


def run():
    fails, fps, native_hits = [], [], 0
    for name, gx, hx in CASES:
        gf = fnx.DiGraph(gx); hf = fnx.DiGraph(hx)
        if set(gx) != set(hx):
            fails.append((name, "SETUP unequal sets")); continue
        if gf._native_difference(hf) is not None:
            native_hits += 1
        cn = canon(nx.difference(gx, hx)); cf = canon(fnx.difference(gf, hf))
        if cn != cf:
            fails.append((name, {"nx": cn, "fnx": cf}))
        fps.append((name, cf))
    sha = hashlib.sha256(json.dumps(fps, sort_keys=True, default=str).encode()).hexdigest()
    print(f"cases={len(CASES)} native_hits={native_hits} mismatches={len(fails)}")
    print(f"golden_sha256={sha}")
    if fails:
        for nm, d in fails[:8]:
            print("MISMATCH", nm, str(d)[:300])
        sys.exit(1)
    print("ALL PARITY OK")


if __name__ == "__main__":
    run()
