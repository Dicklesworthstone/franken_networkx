"""Readwrite matrix: round-trip + CROSS-IMPL interop (nx writes -> fnx
reads, fnx writes -> nx reads), attr VALUE TYPES, graph classes."""
import io
import os
import tempfile

import networkx as nx
import franken_networkx as fnx


def build(mod, cls="Graph"):
    g = getattr(mod, cls)()
    g.add_node(0, label="zero", weight=1.5, flag=True, count=7)
    g.add_node("s")
    g.add_edge(0, 1, weight=2.5, name="e1", active=False, n=3)
    g.add_edge(1, "s", weight=1)
    g.graph["gname"] = "T"
    g.graph["gnum"] = 4
    return g


def rr(g):
    return repr(
        (
            sorted((repr(n), sorted((k, repr(v), type(v).__name__) for k, v in g.nodes[n].items())) for n in g),
            sorted(
                (repr(u), repr(v), sorted((k, repr(x), type(x).__name__) for k, x in d.items()))
                for u, v, d in g.edges(data=True)
            ),
            sorted((k, repr(v), type(v).__name__) for k, v in g.graph.items()),
        )
    )


FORMATS = [
    ("graphml", lambda m, g, p: m.write_graphml(g, p), lambda m, p: m.read_graphml(p)),
    ("gml", lambda m, g, p: m.write_gml(g, p), lambda m, p: m.read_gml(p)),
    ("gexf", lambda m, g, p: m.write_gexf(g, p), lambda m, p: m.read_gexf(p)),
    ("adjlist", lambda m, g, p: m.write_adjlist(g, p), lambda m, p: m.read_adjlist(p)),
    ("edgelist", lambda m, g, p: m.write_edgelist(g, p), lambda m, p: m.read_edgelist(p)),
    ("weighted_edgelist", lambda m, g, p: m.write_weighted_edgelist(g, p), lambda m, p: m.read_weighted_edgelist(p)),
]
tmp = tempfile.mkdtemp(prefix="fnxrw", dir="/data/tmp")
for fname, write, read in FORMATS:
    for direction in ("nx->fnx", "fnx->nx", "fnx->fnx"):
        wmod, rmod = (nx, fnx) if direction == "nx->fnx" else (fnx, nx) if direction == "fnx->nx" else (fnx, fnx)
        p = os.path.join(tmp, f"{fname}-{direction.replace('->','_')}.out")
        try:
            write(wmod, build(wmod), p)
            got = rr(read(rmod, p))
        except Exception as e:
            got = ("ERR", type(e).__name__, str(e)[:60])
        p2 = os.path.join(tmp, f"{fname}-ref.out")
        try:
            write(nx, build(nx), p2)
            ref = rr(read(nx, p2))
        except Exception as e:
            ref = ("ERR", type(e).__name__, str(e)[:60])
        if got != ref:
            print(f"DIVERGES {fname} {direction}:")
            ga, gb = str(got), str(ref)
            for i in range(min(len(ga), len(gb))):
                if ga[i] != gb[i]:
                    print(f"  got=...{ga[max(0,i-40):i+80]}")
                    print(f"  ref=...{gb[max(0,i-40):i+80]}")
                    break
            else:
                print(f"  got={ga[:140]}\n  ref={gb[:140]}")
print("readwrite matrix done")
