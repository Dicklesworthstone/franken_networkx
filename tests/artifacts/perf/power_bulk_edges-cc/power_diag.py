import franken_networkx as fnx, networkx as nx, hashlib
G=nx.barabasi_albert_graph(150,3,seed=1); Gf=fnx.Graph(G)
Pf=fnx.power(Gf,3); Px=nx.power(G,3)
ef=list(Pf.edges()); ex=list(Px.edges())
# same edge SET (normalized)?
sf=set(frozenset(e) for e in ef); sx=set(frozenset(e) for e in ex)
print("edge SET equal:", sf==sx, "| count fnx/nx:", len(ef), len(ex))
print("node SET equal:", set(Pf.nodes())==set(Px.nodes()), "| node order equal:", list(Pf.nodes())==list(Px.nodes()))
# is it just order? sorted edges
nf=sorted(tuple(sorted(e)) for e in ef); nx_=sorted(tuple(sorted(e)) for e in ex)
print("normalized-sorted edges equal:", nf==nx_)
