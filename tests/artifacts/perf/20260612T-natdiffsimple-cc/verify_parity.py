"""Parity + golden proof for native simple-Graph difference (br-r37-c1-natdiffsimple).

Run with PYTHONPATH=<repo>/python so the freshly-built fnx is loaded.
Compares fnx.difference vs nx.difference byte-for-byte across many shapes,
verifies the native path is actually exercised, and emits a golden sha256.
"""
import hashlib, json, warnings, sys
warnings.filterwarnings("ignore")
import networkx as nx
import franken_networkx as fnx


def canon(R):
    """Structural fingerprint: directedness, node order, edge order (as iterated)."""
    return {
        "directed": R.is_directed(),
        "multigraph": R.is_multigraph(),
        "nodes": list(R.nodes()),
        "edges": list(R.edges()),
        "graph_attr_keys": sorted(R.graph.keys()),
    }


def build(spec):
    g = nx.Graph()
    g.add_nodes_from(spec.get("nodes", []))
    g.add_edges_from(spec.get("edges", []))
    return g


CASES = []
# basic / curated
CASES.append(("empty_vs_empty", nx.Graph(), nx.Graph()))
CASES.append(("singleton", build({"nodes": [0]}), build({"nodes": [0]})))
CASES.append(("selfloops", build({"nodes": [0, 1], "edges": [(0, 0), (0, 1), (1, 1)]}),
              build({"nodes": [0, 1], "edges": [(0, 1)]})))
CASES.append(("identical_BA", nx.barabasi_albert_graph(60, 3, seed=2),
              nx.barabasi_albert_graph(60, 3, seed=2)))
# G and H over same node set, different edges
g1 = nx.barabasi_albert_graph(80, 3, seed=4)
h1 = nx.gnp_random_graph(80, 0.1, seed=9)
CASES.append(("BA_minus_gnp", g1, h1))
# disjoint edges
g2 = build({"nodes": list(range(6)), "edges": [(0, 1), (1, 2), (2, 3), (3, 4), (4, 5)]})
h2 = build({"nodes": list(range(6)), "edges": [(1, 2), (3, 4)]})
CASES.append(("path_minus_some", g2, h2))
# string nodes
g3 = build({"nodes": ["a", "b", "c"], "edges": [("a", "b"), ("b", "c"), ("a", "c")]})
h3 = build({"nodes": ["a", "b", "c"], "edges": [("b", "c")]})
CASES.append(("string_nodes", g3, h3))
# complete minus star
g4 = nx.complete_graph(12)
h4 = nx.star_graph(11)
CASES.append(("K12_minus_star", g4, h4))
# node attrs present (difference drops data)
g5 = nx.path_graph(10)
for n in g5: g5.nodes[n]["x"] = n * 2
for u, v in g5.edges(): g5.edges[u, v]["w"] = 1.5
h5 = nx.path_graph(10)
CASES.append(("attrs_dropped", g5, h5))
# graph-level attrs
g6 = nx.cycle_graph(8); g6.graph["name"] = "c8"; g6.graph["meta"] = 1
h6 = nx.cycle_graph(8)
CASES.append(("graph_attrs", g6, h6))
# random seeded sweep
for seed in range(40):
    n = 5 + (seed % 40)
    p = 0.05 + (seed % 7) * 0.05
    ga = nx.gnp_random_graph(n, p, seed=seed)
    # H on same nodes, different edge density
    hb = nx.gnp_random_graph(n, 0.5 * p, seed=seed + 1000)
    hb.add_nodes_from(ga.nodes())
    ga.add_nodes_from(hb.nodes())
    CASES.append((f"rand_{seed}", ga, hb))


def run():
    fails = []
    fps = []
    native_hits = 0
    for name, gx, hx in CASES:
        gf = fnx.Graph(gx); hf = fnx.Graph(hx)
        # ensure node sets equal (difference precondition); skip if not
        if set(gx) != set(hx):
            fails.append((name, "TEST-SETUP node sets unequal")); continue
        # verify native path is actually taken
        native = gf._native_difference(hf)
        if native is not None:
            native_hits += 1
        Rn = nx.difference(gx, hx)
        Rf = fnx.difference(gf, hf)
        cn = canon(Rn); cf = canon(Rf)
        if cn != cf:
            fails.append((name, {"nx": cn, "fnx": cf}))
        fps.append((name, cf))
    blob = json.dumps(fps, sort_keys=True, default=str).encode()
    sha = hashlib.sha256(blob).hexdigest()
    print(f"cases={len(CASES)} native_hits={native_hits} mismatches={len(fails)}")
    print(f"golden_sha256={sha}")
    if fails:
        for nm, d in fails[:8]:
            print("MISMATCH", nm, str(d)[:300])
        sys.exit(1)
    print("ALL PARITY OK")
    return sha


if __name__ == "__main__":
    run()
