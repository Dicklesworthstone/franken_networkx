import random, networkx as nx, franken_networkx as fnx
from franken_networkx.backend import _fnx_to_nx
def struct_only(G):
    if G.is_multigraph():
        H = nx.MultiDiGraph() if G.is_directed() else nx.MultiGraph()
        H.add_nodes_from(G); H.add_edges_from(G.edges(keys=True))
    else:
        H = nx.DiGraph() if G.is_directed() else nx.Graph()
        H.add_nodes_from(G); H.add_edges_from(G.edges())
    return H
from collections import Counter
fails=Counter(); total=Counter()
for seed in range(1500):
    rnd=random.Random(seed); n=rnd.randrange(1,18)
    for cls_f in [fnx.DiGraph,fnx.Graph,fnx.MultiDiGraph,fnx.MultiGraph]:
        gf=cls_f()
        for i in range(n): gf.add_node(i)
        for _ in range(rnd.randrange(0,30)):
            u,v=rnd.randrange(n),rnd.randrange(n); gf.add_edge(u,v)
        t=cls_f.__name__; total[t]+=1
        if list(nx.simple_cycles(_fnx_to_nx(gf)))!=list(nx.simple_cycles(struct_only(gf))): fails[t]+=1
for t in total: print(f"{t:14s}: {fails[t]}/{total[t]} fail")
