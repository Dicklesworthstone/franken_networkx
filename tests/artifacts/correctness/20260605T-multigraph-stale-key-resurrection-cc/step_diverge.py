import random
import networkx as nx, franken_networkx as fnx

def state(G):
    return ([ (str(u),str(v),k,tuple(sorted(d.items()))) for u,v,k,d in G.edges(keys=True,data=True)],
            {str(n): [str(x) for x in G[n]] for n in G})

rng = random.Random(1157)
Gn, Gf = nx.MultiGraph(), fnx.MultiGraph()
n = 5
for i in range(rng.randint(15, 45)):
    op = rng.random()
    a, b = rng.randrange(n), rng.randrange(n)
    if op < 0.35:
        desc = f"add_edge({a},{b},w={a+b})"; Gn.add_edge(a,b,weight=a+b); Gf.add_edge(a,b,weight=a+b)
    elif op < 0.45:
        es = [(rng.randrange(n), rng.randrange(n)) for _ in range(3)]
        desc = f"add_edges_from({es})"; Gn.add_edges_from(es); Gf.add_edges_from(es)
    elif op < 0.55:
        desc = f"remove_node({a})"
        if a in Gn: Gn.remove_node(a)
        if a in Gf: Gf.remove_node(a)
    elif op < 0.62:
        desc = f"remove_edge({a},{b})"
        if Gn.has_edge(a,b): Gn.remove_edge(a,b)
        if Gf.has_edge(a,b): Gf.remove_edge(a,b)
    elif op < 0.68:
        es = [(0,1),(1,2)]; desc = "remove_edges_from"
        Gn.remove_edges_from([e for e in es if Gn.has_edge(*e)])
        Gf.remove_edges_from([e for e in es if Gf.has_edge(*e)])
    elif op < 0.74:
        desc = "update"; Gn.update([(3,4)],[3,4]); Gf.update([(3,4)],[3,4])
    elif op < 0.82:
        sub = [x for x in range(n) if rng.random() < 0.6]
        desc = f"subgraph({sub}).copy()"
        Gn = Gn.subgraph([x for x in sub if x in Gn]).copy()
        Gf = Gf.subgraph([x for x in sub if x in Gf]).copy()
    elif op < 0.88:
        desc = "copy"; Gn, Gf = Gn.copy(), Gf.copy()
    elif op < 0.92:
        desc = f"nodeattr({a})"
        if a in Gn: Gn.nodes[a]["c"]="z"; Gf.nodes[a]["c"]="z"
    elif op < 0.96:
        desc = "clear"; Gn.clear(); Gf.clear()
    else:
        desc = f"add_edge_extra({a},{b})"
        if Gn.has_edge(a,b): Gn.add_edge(a,b,extra=1); Gf.add_edge(a,b,extra=1)
    sn, sf = state(Gn), state(Gf)
    if sn != sf:
        print(f"DIVERGED at step {i}: {desc}")
        print(" nx :", sn)
        print(" fnx:", sf)
        break
    print(f"ok {i}: {desc}")
