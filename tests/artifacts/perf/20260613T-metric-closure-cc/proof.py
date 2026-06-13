"""Order-sensitive byte-parity proof for the metric_closure native route.

Compares a candidate native-all_pairs_dijkstra implementation against the
CURRENT delegated fnx.approximation.metric_closure across many graph shapes.
Checks: node order, UNSORTED edge insertion order, per-edge distance + path,
edge-attr key set, and graph-level attrs. Emits a sha256 golden over the
full ordered structure.
"""
import sys, json, hashlib, warnings
import networkx as nx
import networkx.algorithms.approximation as nxa
import franken_networkx as fnx
import franken_networkx.approximation as fa
from franken_networkx.readwrite import _from_nx_graph

warnings.filterwarnings("ignore")


def _native_metric_closure(G, weight="weight"):
    # candidate route (mirror of the production wrapper under test)
    apd = fnx._raw_all_pairs_dijkstra(G, weight=weight)
    nodes = list(G)
    n = len(nodes)
    first = nodes[0]
    if len(apd[first][0]) != n:
        raise nx.NetworkXError(
            "G is not a connected graph. metric_closure is not defined."
        )
    M = fnx.Graph()
    Gnodes = set(G)
    Gnodes.remove(first)
    dist0, path0 = apd[first]
    edges = [(first, v, {"distance": dist0[v], "path": path0[v]}) for v in Gnodes]
    for u in nodes[1:]:
        Gnodes.remove(u)
        dist, path = apd[u]
        edges.extend((u, v, {"distance": dist[v], "path": path[v]}) for v in Gnodes)
    M.add_edges_from(edges)
    return M


def ordered_struct(M):
    return {
        "nodes": list(M.nodes()),
        "edges": [
            [u, v, M.edges[u, v].get("distance"), list(M.edges[u, v].get("path")),
             sorted(M.edges[u, v].keys())]
            for u, v in M.edges()
        ],
        "graph": dict(M.graph),
    }


def make(name):
    if name == "karate":
        g = nx.karate_club_graph()
    elif name == "petersen":
        g = nx.petersen_graph()
    elif name.startswith("ws"):
        _, n, s = name.split("_")
        g = nx.connected_watts_strogatz_graph(int(n), 6, 0.2, seed=int(s))
    elif name.startswith("path"):
        g = nx.path_graph(int(name.split("_")[1]))
    elif name.startswith("cycle"):
        g = nx.cycle_graph(int(name.split("_")[1]))
    elif name.startswith("complete"):
        g = nx.complete_graph(int(name.split("_")[1]))
    elif name.startswith("grid"):
        g = nx.convert_node_labels_to_integers(nx.grid_2d_graph(5, 5))
    elif name == "wkarate":
        g = nx.karate_club_graph()
        for i, (u, v) in enumerate(g.edges()):
            g.edges[u, v]["weight"] = float(1 + (i % 7))
    else:
        raise ValueError(name)
    fg = fnx.Graph()
    fg.add_nodes_from(g.nodes())
    for u, v, d in g.edges(data=True):
        if "weight" in d:
            fg.add_edge(u, v, weight=d["weight"])
        else:
            fg.add_edge(u, v)
    return fg, g


CASES = [
    "karate", "petersen", "path_8", "cycle_12", "complete_6", "grid", "wkarate",
    "ws_60_1", "ws_60_7", "ws_150_42", "ws_300_3",
]


def main():
    h = hashlib.sha256()
    allmatch = True
    report = {}
    for name in CASES:
        fg, g = make(name)
        weight = "weight"
        cur = fa.metric_closure(fg, weight=weight)
        cand = _native_metric_closure(fg, weight=weight)
        # nx reference (distance-only, since path ties may differ across impls)
        sc = ordered_struct(cur)
        sk = ordered_struct(cand)
        match = (sc == sk)
        allmatch = allmatch and match
        report[name] = {
            "match_cur_eq_cand": match,
            "n_edges": cur.number_of_edges(),
        }
        if not match:
            # localize first diff
            for key in ("nodes", "graph"):
                if sc[key] != sk[key]:
                    report[name][f"diff_{key}"] = True
            if sc["edges"] != sk["edges"]:
                for i, (a, b) in enumerate(zip(sc["edges"], sk["edges"])):
                    if a != b:
                        report[name]["first_edge_diff"] = {"i": i, "cur": a, "cand": b}
                        break
        h.update(json.dumps(ordered_struct(cand), sort_keys=False, default=str).encode())
    golden = h.hexdigest()
    out = {"all_match": allmatch, "golden_sha256": golden, "cases": report}
    print(json.dumps(out, indent=2, default=str))
    with open(sys.argv[1] if len(sys.argv) > 1 else "/tmp/mc_proof.json", "w") as f:
        json.dump(out, f, indent=2, default=str)
    sys.exit(0 if allmatch else 1)


if __name__ == "__main__":
    main()
