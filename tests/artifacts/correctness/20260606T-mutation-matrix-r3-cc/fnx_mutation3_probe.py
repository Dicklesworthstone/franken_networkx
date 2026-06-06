"""Mutation-surface matrix round 3: remove_edge key variants,
clear/clear_edges, SubgraphView mutation passthrough, edge subscript
mutation, remove_node state."""
import networkx as nx
import franken_networkx as fnx


def base(mod, cls):
    g = getattr(mod, cls)()
    g.add_edge(0, 1, w=1)
    g.add_edge(1, 2, w=2)
    if g.is_multigraph():
        g.add_edge(0, 1, w=9)        # parallel auto key 1
        g.add_edge(0, 1, key="k", w=3)
    g.add_node("iso", t=1)
    g.graph["ga"] = 5
    return g


def state(g, err):
    if g.is_multigraph():
        edges = sorted(repr(e) for e in g.edges(keys=True, data=True))
    else:
        edges = sorted(repr(e) for e in g.edges(data=True))
    return (err, sorted((repr(n), repr(dict(g.nodes[n]))) for n in g), edges, dict(g.graph))


MUTS = [
    ("re: by key str", lambda g: g.remove_edge(0, 1, key="k") if g.is_multigraph() else None),
    ("re: by key int", lambda g: g.remove_edge(0, 1, key=1) if g.is_multigraph() else None),
    ("re: by key missing", lambda g: g.remove_edge(0, 1, key="zz") if g.is_multigraph() else None),
    ("re: key on missing edge", lambda g: g.remove_edge(5, 6, key=0) if g.is_multigraph() else None),
    ("re: no key removes last", lambda g: g.remove_edge(0, 1) if g.is_multigraph() else None),
    ("clear", lambda g: g.clear()),
    ("clear_edges", lambda g: g.clear_edges()),
    ("rn: with attrs+edges", lambda g: g.remove_node(1)),
    ("edge subscript del", lambda g: g[0][1].pop("w") if not g.is_multigraph() else g[0][1][0].pop("w")),
    ("nodes subscript update", lambda g: g.nodes["iso"].update({"t": 9, "u": 1})),
]
for cls in ("Graph", "DiGraph", "MultiGraph", "MultiDiGraph"):
    for label, fn in MUTS:
        gn, gf = base(nx, cls), base(fnx, cls)
        if "re:" in label and not gn.is_multigraph():
            continue
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
# SubgraphView passthrough: mutating the PARENT reflects in the view; view itself is frozen
for cls in ("Graph", "DiGraph"):
    gn, gf = base(nx, cls), base(fnx, cls)
    vn, vf = gn.subgraph([0, 1, 2]), gf.subgraph([0, 1, 2])
    gn.add_edge(0, 2, q=1); gf.add_edge(0, 2, q=1)
    a = (sorted(repr(e) for e in vf.edges(data=True)), sorted(map(repr, vf)))
    b = (sorted(repr(e) for e in vn.edges(data=True)), sorted(map(repr, vn)))
    if a != b: print(f"DIVERGES {cls} view-reflect: {a} {b}")
    try: vn.add_edge(9, 9); en = None
    except Exception as e: en = type(e).__name__
    try: vf.add_edge(9, 9); ef = None
    except Exception as e: ef = type(e).__name__
    if en != ef: print(f"DIVERGES {cls} view-frozen: {en} {ef}")
print("matrix3 done")
