"""Partial-error-state parity matrix for mutation APIs beyond
add_edges_from (proven recipe from br-r37-c1-baqyi): malformed cases x
4 classes x (error type+message, node set, edge set with data)."""
import networkx as nx
import franken_networkx as fnx


def base(mod, cls):
    g = getattr(mod, cls)()
    g.add_edge(0, 1, w=1)
    g.add_edge(1, 2, w=2)
    g.add_node("iso")
    return g


def state(g, err):
    if g.is_multigraph():
        edges = sorted(repr(e) for e in g.edges(keys=True, data=True))
    else:
        edges = sorted(repr(e) for e in g.edges(data=True))
    nodes = sorted((repr(n), repr(dict(g.nodes[n]))) for n in g)
    return (err, nodes, edges)


MUTS = [
    # (label, callable(g))
    ("ren: valid+bad mid", lambda g: g.remove_edges_from([(0, 1), None, (1, 2)])),
    ("ren: 1-tuple mid", lambda g: g.remove_edges_from([(0, 1), (2,), (1, 2)])),
    ("ren: unhash mid", lambda g: g.remove_edges_from([(0, 1), ([1], 2), (1, 2)])),
    ("rnf: unhash mid", lambda g: g.remove_nodes_from([0, [1], 2])),
    ("rnf: missing mid ok", lambda g: g.remove_nodes_from([0, 99, 2])),
    ("anf: unhash mid", lambda g: g.add_nodes_from([5, [6], 7])),
    ("anf: none mid", lambda g: g.add_nodes_from([5, None, 7])),
    ("anf: tuple-attr bad", lambda g: g.add_nodes_from([(5, {"a": 1}), (6, 1.5), 7])),
    ("upd: edges bad mid", lambda g: g.update(edges=[(5, 6), (7, None)])),
    ("upd: nodes bad mid", lambda g: g.update(nodes=[5, [6]])),
    ("re: missing", lambda g: g.remove_edge(0, 99)),
    ("rn: missing", lambda g: g.remove_node(99)),
    ("awef: bad weight mid", lambda g: g.add_weighted_edges_from([(5, 6, 1.0), (7, 8), (8, 9, 2.0)])),
    ("awef: unhash mid", lambda g: g.add_weighted_edges_from([(5, 6, 1.0), ([7], 8, 2.0)])),
]

for cls in ("Graph", "DiGraph", "MultiGraph", "MultiDiGraph"):
    for label, fn in MUTS:
        gn, gf = base(nx, cls), base(fnx, cls)
        try:
            fn(gn)
            en = None
        except Exception as e:
            en = (type(e).__name__, str(e)[:50])
        try:
            fn(gf)
            ef = None
        except Exception as e:
            ef = (type(e).__name__, str(e)[:50])
        sn, sf = state(gn, en), state(gf, ef)
        if sn != sf:
            print(f"DIVERGES {cls} {label}:\n  nx={sn}\n  fx={sf}")
print("matrix done")
