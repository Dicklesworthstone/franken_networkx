"""Mutation-cycle stress: interleaved add/remove/clear on MultiDiGraph, mixed keys."""
import random
import networkx as nx
import franken_networkx as fnx

rnd = random.Random(424242)
def mk():
    b = rnd.randrange(10)
    return rnd.choice([b, float(b), f"s{b}"])

fails = 0
for trial in range(150):
    gn, gf = nx.MultiDiGraph(), fnx.MultiDiGraph()
    for step in range(rnd.randrange(5, 40)):
        op = rnd.random()
        if op < 0.55:
            u, v = mk(), mk()
            gn.add_edge(u, v); gf.add_edge(u, v)
        elif op < 0.7 and gn.number_of_edges():
            u, v, k = rnd.choice(list(gn.edges(keys=True)))
            gn.remove_edge(u, v, k); gf.remove_edge(u, v, k)
        elif op < 0.8 and len(gn):
            n = rnd.choice(list(gn.nodes()))
            gn.remove_node(n); gf.remove_node(n)
        elif op < 0.85:
            gn.clear_edges(); gf.clear_edges()
        elif op < 0.95:
            gn, gf = gn.copy(), gf.copy()
        else:
            gn, gf = gn.reverse(), gf.reverse()
    a = ({repr(n): [repr(x) for x in gn.succ[n]] for n in gn},
         {repr(n): [repr(x) for x in gn.pred[n]] for n in gn},
         [tuple(map(repr, e)) for e in gn.edges(keys=True, data=True)])
    b = ({repr(n): [repr(x) for x in gf.succ[n]] for n in gf},
         {repr(n): [repr(x) for x in gf.pred[n]] for n in gf},
         [tuple(map(repr, e)) for e in gf.edges(keys=True, data=True)])
    if a != b:
        fails += 1
        if fails <= 2:
            print("FAIL", trial)
            for x, y in zip(a, b):
                if x != y: print(" nx :", str(x)[:180]); print(" fnx:", str(y)[:180]); break
print("mutation trials=150 fails:", fails)
