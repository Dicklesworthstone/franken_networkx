"""br-r37-c1-z6uka stress: mixed hash-colliding keys via batch paths, all classes."""
import random
import networkx as nx
import franken_networkx as fnx

rnd = random.Random(987654321)
fails = []

def canon(g):
    out = [repr([(repr(n), dict(a)) for n, a in g.nodes(data=True)])]
    out.append(repr([(repr(u), repr(v)) for u, v in g.edges()]))
    out.append(repr({repr(n): [repr(x) for x in g[n]] for n in g}))
    if g.is_directed():
        out.append(repr({repr(n): [repr(x) for x in g.pred[n]] for n in g}))
    return "\n".join(out)

def mk():
    base = rnd.randrange(12)
    return rnd.choice([base, float(base), bool(base % 2) if base < 2 else base, f"s{base}"])

for trial in range(400):
    cls = rnd.choice(["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
    n_edges = rnd.choice([8, 9, 12, 30, 60])  # batch gate >= 8
    style = rnd.randrange(3)
    edges = []
    for _ in range(n_edges):
        u, v = mk(), mk()
        if style == 0:
            edges.append((u, v))
        elif style == 1:
            edges.append((u, v, {"w": rnd.random()}))
        else:
            edges.append(rnd.choice([(u, v), (u, v, {"w": rnd.randrange(5)}), (u, v, {})]))
    pre_nodes = [mk() for _ in range(rnd.randrange(4))]
    gn, gf = getattr(nx, cls)(), getattr(fnx, cls)()
    gn.add_nodes_from(pre_nodes); gf.add_nodes_from(pre_nodes)
    gn.add_edges_from(edges); gf.add_edges_from(edges)
    # second batch reusing colliding variants
    edges2 = [(mk(), mk()) for _ in range(9)]
    gn.add_edges_from(edges2); gf.add_edges_from(edges2)
    cn, cf = canon(gn), canon(gf)
    if cn != cf:
        fails.append(trial)
        if len(fails) <= 3:
            print(f"FAIL trial={trial} cls={cls}")
            for a, b in zip(cn.split("\n"), cf.split("\n")):
                if a != b:
                    print("  nx :", a[:200]); print("  fnx:", b[:200]); break
print("trials=400 fails:", len(fails), fails[:20])
