import random
from collections import Counter
import networkx as nx
import franken_networkx as fnx

rnd = random.Random(987654321)
facets = ["nodes", "edges", "adj", "pred"]
fail_by = Counter()

def canon_parts(g):
    p = {"nodes": repr([(repr(n), dict(a)) for n, a in g.nodes(data=True)]),
         "edges": repr([(repr(u), repr(v)) for u, v in g.edges()]),
         "adj": repr({repr(n): [repr(x) for x in g[n]] for n in g})}
    p["pred"] = repr({repr(n): [repr(x) for x in g.pred[n]] for n in g}) if g.is_directed() else ""
    return p

def mk():
    base = rnd.randrange(12)
    return rnd.choice([base, float(base), bool(base % 2) if base < 2 else base, f"s{base}"])

for trial in range(400):
    cls = rnd.choice(["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
    n_edges = rnd.choice([8, 9, 12, 30, 60])
    style = rnd.randrange(3)
    edges = []
    for _ in range(n_edges):
        u, v = mk(), mk()
        edges.append((u, v) if style == 0 else (u, v, {"w": rnd.random()}) if style == 1
                     else rnd.choice([(u, v), (u, v, {"w": rnd.randrange(5)}), (u, v, {})]))
    pre = [mk() for _ in range(rnd.randrange(4))]
    gn, gf = getattr(nx, cls)(), getattr(fnx, cls)()
    gn.add_nodes_from(pre); gf.add_nodes_from(pre)
    gn.add_edges_from(edges); gf.add_edges_from(edges)
    e2 = [(mk(), mk()) for _ in range(9)]
    gn.add_edges_from(e2); gf.add_edges_from(e2)
    pn, pf = canon_parts(gn), canon_parts(gf)
    for f in facets:
        if pn[f] != pf[f]:
            fail_by[(cls, f)] += 1
print(dict(fail_by))
