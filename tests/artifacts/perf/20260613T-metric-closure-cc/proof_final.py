"""Final order-sensitive byte-parity proof for the metric_closure native route.

Compares the shipped concrete ``_ApproximationNamespace.metric_closure``
(native ``_raw_all_pairs_dijkstra`` route) against the exact previous
delegating path ``_from_nx_graph(nx.metric_closure(_networkx_graph_for_parity(G)))``
across many graph shapes. Checks node order, UNSORTED edge insertion order,
per-edge distance + path, edge-attr key set, and graph attrs. Emits a sha256.
"""
import sys, json, hashlib, warnings
import networkx as nx
import networkx.algorithms.approximation as nxa
import franken_networkx as fnx
from franken_networkx.readwrite import _from_nx_graph

warnings.filterwarnings("ignore")


def old_path(G, weight="weight"):
    return _from_nx_graph(
        nxa.metric_closure(fnx._networkx_graph_for_parity(G), weight=weight)
    )


def ostruct(M):
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
    elif name == "wkarate":
        g = nx.karate_club_graph()
        for i, (u, v) in enumerate(g.edges()):
            g.edges[u, v]["weight"] = float(1 + (i % 7))
    elif name.startswith("ws"):
        _, n, s = name.split("_")
        g = nx.connected_watts_strogatz_graph(int(n), 6, 0.2, seed=int(s))
    elif name == "grid":
        g = nx.convert_node_labels_to_integers(nx.grid_2d_graph(5, 5))
    elif name.startswith("path"):
        g = nx.path_graph(int(name.split("_")[1]))
    elif name.startswith("complete"):
        g = nx.complete_graph(int(name.split("_")[1]))
    fg = fnx.Graph()
    fg.add_nodes_from(g.nodes())
    for u, v, d in g.edges(data=True):
        fg.add_edge(u, v, weight=d["weight"]) if "weight" in d else fg.add_edge(u, v)
    return fg


CASES = ["karate", "petersen", "wkarate", "grid", "path_8", "complete_6",
         "ws_60_1", "ws_60_7", "ws_150_42", "ws_300_3"]


def main():
    h = hashlib.sha256()
    allok = True
    report = {}
    for nm in CASES:
        fg = make(nm)
        new = ostruct(fnx.approximation.metric_closure(fg))
        old = ostruct(old_path(fg))
        ok = (new == old)
        allok = allok and ok
        report[nm] = {"match_new_eq_old": ok, "n_edges": len(new["edges"])}
        if not ok:
            for i, (x, y) in enumerate(zip(new["edges"], old["edges"])):
                if x != y:
                    report[nm]["first_diff"] = {"i": i, "new": x, "old": y}
                    break
        h.update(json.dumps(new, default=str).encode())
    out = {"all_match_new_eq_old": allok, "golden_sha256": h.hexdigest(), "cases": report}
    print(json.dumps(out, indent=2, default=str))
    with open(sys.argv[1] if len(sys.argv) > 1 else "/tmp/p.json", "w") as f:
        json.dump(out, f, indent=2, default=str)
    sys.exit(0 if allok else 1)


if __name__ == "__main__":
    main()
