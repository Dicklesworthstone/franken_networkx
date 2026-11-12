import warnings; warnings.filterwarnings("ignore")
import networkx as nx, franken_networkx as fnx, random

def cmp(gn, gf, tag):
    rn = gn.reverse(); rf = gf.reverse()
    en = [(u,v) for u,v in rn.edges()]
    ef = [(u,v) for u,v in rf.edges()]
    pn = {x: list(rn.pred[x]) for x in rn}
    pf = {x: list(rf.pred[x]) for x in rf}
    sn = {x: list(rn.succ[x]) for x in rn}
    sf = {x: list(rf.succ[x]) for x in rf}
    nn = list(rn.nodes()); nf = list(rf.nodes())
    ok = en==ef and pn==pf and sn==sf and nn==nf
    print(f"{tag}: edges={en==ef} succ={sn==sf} pred={pn==pf} nodes={nn==nf} -> {'OK' if ok else 'FAIL'}")
    if not ok and len(en)<40:
        print("  nx edges:", en); print("  fx edges:", ef)
    return ok

allok = True
# scrambled insertion order
for seed in range(8):
    r = random.Random(seed)
    edges = [(r.randint(0,15), r.randint(0,15)) for _ in range(40)]
    gn = nx.DiGraph(); gf = fnx.DiGraph()
    gn.add_nodes_from(range(16)); gf.add_nodes_from(range(16))
    for (u,v) in edges:
        gn.add_edge(u,v); gf.add_edge(u,v)
    allok &= cmp(gn, gf, f"scramble{seed}")
# self loops + string labels
gn = nx.DiGraph([("a","b"),("b","c"),("a","a"),("c","a"),("b","b")])
gf = fnx.DiGraph([("a","b"),("b","c"),("a","a"),("c","a"),("b","b")])
allok &= cmp(gn, gf, "selfloop_str")
# reverse-insertion (worst case for pred order)
gn = nx.DiGraph(); gf = fnx.DiGraph()
for u in range(9,-1,-1):
    for v in range(10):
        gn.add_edge(u,v); gf.add_edge(u,v)
allok &= cmp(gn, gf, "reverse_major")
# isolated nodes
gn = nx.DiGraph(); gf = fnx.DiGraph()
gn.add_nodes_from([5,3,1]); gf.add_nodes_from([5,3,1])
gn.add_edge(3,1); gf.add_edge(3,1)
allok &= cmp(gn, gf, "isolated")
print("ALL_OK", allok)
