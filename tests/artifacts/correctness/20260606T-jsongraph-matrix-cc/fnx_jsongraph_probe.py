"""JSON-graph family matrix: node_link/adjacency/cytoscape/tree data+graph
round-trips, CROSS-IMPL (nx data -> fnx graph, fnx data -> nx graph),
typed attrs, all four classes where applicable."""
import json

import networkx as nx
import franken_networkx as fnx


def build(mod, cls="Graph"):
    g = getattr(mod, cls)()
    g.add_node(0, label="zero", weight=1.5, flag=True)
    g.add_node("s")
    g.add_edge(0, 1, weight=2.5, name="e1")
    g.add_edge(1, "s")
    if g.is_multigraph():
        g.add_edge(0, 1, weight=9.0)
    g.graph["gname"] = "T"
    return g


def rr(g):
    if g.is_multigraph():
        edges = sorted(
            (repr(u), repr(v), repr(k), sorted((a, repr(x), type(x).__name__) for a, x in d.items()))
            for u, v, k, d in g.edges(keys=True, data=True)
        )
    else:
        edges = sorted(
            (repr(u), repr(v), sorted((a, repr(x), type(x).__name__) for a, x in d.items()))
            for u, v, d in g.edges(data=True)
        )
    return repr((
        sorted((repr(n), sorted((a, repr(x), type(x).__name__) for a, x in g.nodes[n].items())) for n in g),
        edges,
        sorted((a, repr(x)) for a, x in g.graph.items()),
        g.is_directed(), g.is_multigraph(),
    ))


def js(x):
    return json.loads(json.dumps(x))  # normalize via JSON like real usage


CASES = []
for cls in ("Graph", "DiGraph", "MultiGraph", "MultiDiGraph"):
    CASES += [
        (f"node_link {cls}", cls,
         lambda m, g: m.node_link_data(g, edges="links"),
         lambda m, d: m.node_link_graph(js(d), edges="links")),
        (f"adjacency {cls}", cls,
         lambda m, g: m.adjacency_data(g),
         lambda m, d: m.adjacency_graph(js(d))),
        (f"cytoscape {cls}", cls,
         lambda m, g: m.cytoscape_data(g),
         lambda m, d: m.cytoscape_graph(js(d))),
    ]
CASES.append(("tree Graph", "DiGraph",
              lambda m, g: m.tree_data(m.bfs_tree(g, 0), 0),
              lambda m, d: m.tree_graph(js(d))))
for name, cls, dump, load in CASES:
    for direction in ("nx->fnx", "fnx->nx", "fnx->fnx"):
        wmod, rmod = (nx, fnx) if direction == "nx->fnx" else (fnx, nx) if direction == "fnx->nx" else (fnx, fnx)
        try:
            got = rr(load(rmod, dump(wmod, build(wmod, cls))))
        except Exception as e:
            got = ("ERR", type(e).__name__, str(e)[:70])
        try:
            ref = rr(load(nx, dump(nx, build(nx, cls))))
        except Exception as e:
            ref = ("ERR", type(e).__name__, str(e)[:70])
        if got != ref:
            print(f"DIVERGES {name} {direction}:")
            ga, gb = str(got), str(ref)
            for i in range(min(len(ga), len(gb))):
                if ga[i] != gb[i]:
                    print(f"  got=...{ga[max(0,i-30):i+90]}")
                    print(f"  ref=...{gb[max(0,i-30):i+90]}")
                    break
            else:
                print(f"  got={ga[:150]}\n  ref={gb[:150]}")
print("jsongraph matrix done")
