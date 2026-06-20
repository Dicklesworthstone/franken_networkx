import random, networkx as nx, franken_networkx as fnx
def canon(C):
    # nodes with members sets, edges, mapping, edge ITERATION order
    nodes = [(n, frozenset(C.nodes[n]['members'])) for n in C.nodes()]
    edges = list(C.edges())
    mapping = dict(C.graph['mapping'])
    return nodes, edges, mapping
fails=0; total=0
for seed in range(2000):
    rnd=random.Random(seed); n=rnd.randrange(1,30)
    gn=nx.MultiDiGraph(); gf=fnx.MultiDiGraph()
    for i in range(n): gn.add_node(i); gf.add_node(i)
    for _ in range(rnd.randrange(0,55)):
        u,v=rnd.randrange(n),rnd.randrange(n)
        gn.add_edge(u,v); gf.add_edge(u,v)  # parallels + self-loops
    total+=1
    cn=canon(nx.condensation(gn)); cf=canon(fnx.condensation(gf))
    if cn!=cf:
        fails+=1
        if fails<=5:
            print("seed",seed)
            if cn[0]!=cf[0]: print(" nodes/members differ")
            if cn[1]!=cf[1]: print("  edges nx",cn[1][:6],"\n  edges fnx",cf[1][:6])
            if cn[2]!=cf[2]: print("  mapping differ")
print(f"MultiDiGraph condensation parity: {fails}/{total} fail")
