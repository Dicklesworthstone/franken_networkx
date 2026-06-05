import networkx as nx, franken_networkx as fnx

def canon(g):
    return [(u, v, k, tuple(sorted(d.items()))) for u, v, k, d in g.edges(keys=True, data=True)]

def trial(name, ops):
    gn, gf = nx.MultiGraph(), fnx.MultiGraph()
    for op in ops:
        getattr(gn, op[0])(*op[1:])
        getattr(gf, op[0])(*op[1:])
    cn, cf = canon(gn), canon(gf)
    flag = "OK " if cn == cf else "DIV"
    print(f"{flag} {name}")
    if cn != cf:
        print("  nx :", cn)
        print("  fnx:", cf)

# straight remove-then-readd
trial("A", [("add_edge", 4, 3), ("add_edge", 4, 3), ("remove_edge", 4, 3),
            ("add_edge", 4, 3), ("add_edge", 4, 3)])
# weighted key removed, then readds
import functools
gn, gf = nx.MultiGraph(), fnx.MultiGraph()
for g in (gn, gf):
    g.add_edge(4, 3)
    g.add_edge(4, 3, weight=7)
    g.remove_edge(4, 3)            # removes key 1 (weighted)
    g.add_edges_from([(3, 4), (3, 4)])  # reversed orientation adds
    g.add_edge(4, 3)
cn, cf = canon(gn), canon(gf)
print("B", "OK" if cn == cf else "DIV")
if cn != cf:
    print("  nx :", cn); print("  fnx:", cf)
