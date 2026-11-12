"""Golden + nx-parity proof for MultiGraph attributed add_edges_from batch.

Produces an order-sensitive structural signature of a MultiGraph built via
add_edges_from across many shapes, and checks it byte-matches BOTH:
  (a) the same graph built edge-by-edge with add_edge (the per-edge contract), and
  (b) networkx.MultiGraph (drop-in parity).
Also checks edge-data mutability (G[u][v][k] is a live, fnx-owned dict that does
NOT alias the user's input dict).

Run before AND after the change: golden sha must be identical.
"""
import sys, json, hashlib, warnings
import networkx as nx
import franken_networkx as fnx
warnings.filterwarnings("ignore")


def sig_multigraph(G):
    # order-sensitive: node order, then edges(keys=True,data=True) order with data
    nodes = list(G.nodes())
    edges = []
    for u, v, k, d in G.edges(keys=True, data=True):
        edges.append([u, v, k, sorted((str(kk), repr(vv)) for kk, vv in d.items())])
    # adjacency view: per node, neighbor -> {key: data}
    adj = []
    for n in G.nodes():
        row = []
        for nbr, keydict in G[n].items():
            row.append([nbr, sorted(keydict.keys())])
        adj.append([n, row])
    return {"nodes": nodes, "edges": edges, "adj": adj,
            "n_edges": G.number_of_edges(), "graph": dict(G.graph)}


CASES = {
    # name: (edge_bunch, kwargs)
    "plain_8": ([(i, i + 1) for i in range(8)], {}),
    "attr_simple": ([(i, i + 1, {"w": float(i)}) for i in range(10)], {}),
    "attr_mixed_plain": ([(0, 1, {"w": 1}), (1, 2), (2, 3, {"x": "a"}), (3, 4),
                          (0, 1, {"w": 2}), (5, 6), (6, 7, {}), (7, 8, {"y": [1, 2]}),
                          (8, 9), (9, 10, {"z": 3.5})], {}),
    "parallel_attr": ([(0, 1, {"w": i}) for i in range(12)], {}),
    "selfloops": ([(0, 0, {"w": 1}), (1, 1), (2, 2, {"x": 2}), (0, 0, {"w": 2}),
                   (3, 3), (4, 4, {"k": "v"}), (5, 5), (6, 6, {"a": 1})], {}),
    "str_nodes": ([("a", "b", {"w": 1}), ("b", "c"), ("c", "d", {"x": 2}),
                   ("a", "b", {"w": 9}), ("d", "e"), ("e", "f", {"y": 3}),
                   ("f", "g"), ("g", "h", {"z": 4})], {}),
    "tuple_nodes": ([((0, 0), (0, 1), {"w": 1}), ((0, 1), (0, 2)),
                     ((0, 2), (0, 3), {"x": 2}), ((0, 0), (0, 1), {"w": 5}),
                     ((1, 0), (1, 1)), ((1, 1), (1, 2), {"y": 3}),
                     ((2, 0), (2, 1)), ((2, 1), (2, 2), {"z": 4})], {}),
    "global_attr": ([(i, i + 1, {"w": i}) for i in range(10)], {"color": "red"}),
    "global_attr_override": ([(0, 1, {"color": "blue"}), (1, 2), (2, 3, {"w": 1}),
                              (3, 4), (4, 5), (5, 6), (6, 7), (7, 8)], {"color": "red"}),
    "reversed_pairs": ([(1, 0, {"w": 1}), (2, 1), (0, 1, {"w": 2}), (3, 2, {"x": 1}),
                        (1, 2), (4, 3), (5, 4), (3, 4, {"y": 2})], {}),
}


def build_fnx_batch(bunch, kwargs):
    g = fnx.MultiGraph()
    g.add_edges_from(bunch, **kwargs)
    return g


def build_fnx_peredge(bunch, kwargs):
    g = fnx.MultiGraph()
    for e in bunch:
        if len(e) == 3 and isinstance(e[2], dict):
            u, v, d = e
            g.add_edge(u, v, **{**kwargs, **d})
        elif len(e) == 2:
            u, v = e
            g.add_edge(u, v, **kwargs)
        else:
            raise AssertionError(e)
    return g


def build_nx(bunch, kwargs):
    g = nx.MultiGraph()
    g.add_edges_from(bunch, **kwargs)
    return g


def main():
    h = hashlib.sha256()
    report = {}
    ok_all = True
    for name, (bunch, kwargs) in CASES.items():
        gb = build_fnx_batch(bunch, kwargs)
        sb = sig_multigraph(gb)
        # parity vs per-edge fnx and vs nx
        try:
            sp = sig_multigraph(build_fnx_peredge(bunch, kwargs))
        except Exception as e:
            sp = {"err": repr(e)}
        sn = sig_multigraph(build_nx(bunch, kwargs))
        eq_peredge = (sb == sp)
        eq_nx = (sb == sn)
        # mutability: G[u][v][k] is live + does not alias input dict
        mut_ok = True
        if name == "attr_simple":
            inp = {"w": 99.0}
            gm = fnx.MultiGraph(); gm.add_edges_from([(0, 1, inp)] + [(2, 3)] * 7)
            d = gm[0][1][0]
            d["new"] = 1  # mutate stored -> persists
            inp["leak"] = 2  # mutate input -> must NOT appear in stored
            mut_ok = (gm[0][1][0].get("new") == 1) and ("leak" not in gm[0][1][0])
        report[name] = {"eq_peredge": eq_peredge, "eq_nx": eq_nx,
                        "n_edges": sb["n_edges"], "mut_ok": mut_ok}
        ok_all = ok_all and eq_peredge and eq_nx and mut_ok
        h.update(json.dumps(sb, default=str, sort_keys=False).encode())
        if not (eq_peredge and eq_nx):
            # localize
            if sb.get("edges") != sn.get("edges"):
                for i, (a, b) in enumerate(zip(sb["edges"], sn["edges"])):
                    if a != b:
                        report[name]["first_edge_diff_vs_nx"] = {"i": i, "fnx": a, "nx": b}
                        break
            if sb.get("nodes") != sn.get("nodes"):
                report[name]["nodes_diff_vs_nx"] = {"fnx": sb["nodes"][:6], "nx": sn["nodes"][:6]}
    out = {"all_ok": ok_all, "golden_sha256": h.hexdigest(), "cases": report}
    print(json.dumps(out, indent=2, default=str))
    with open(sys.argv[1] if len(sys.argv) > 1 else "/tmp/mg.json", "w") as f:
        json.dump(out, f, indent=2, default=str)
    sys.exit(0 if ok_all else 1)


if __name__ == "__main__":
    main()
