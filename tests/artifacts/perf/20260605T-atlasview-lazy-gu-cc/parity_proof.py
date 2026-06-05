import franken_networkx as fnx, networkx as nx, random
mism=0
def eq(a,b,label):
    global mism
    if a!=b:
        mism+=1; print(f"MISMATCH {label}: fnx={a!r} nx={b!r}")
# build identical graphs
rng=random.Random(3)
Gf=fnx.Graph(); Gn=nx.Graph()
for u,v in [(0,1),(1,2),(2,0),(2,3),(3,4),(0,5)]:
    w=rng.random(); Gf.add_edge(u,v,weight=w,color='r'); Gn.add_edge(u,v,weight=w,color='r')
Gf.add_node(9); Gn.add_node(9)  # isolated
# AtlasView API parity
for u in [0,1,2,3,4,9]:
    av_f, av_n = Gf[u], Gn[u]
    eq(len(av_f), len(av_n), f"len G[{u}]")
    eq(sorted(av_f), sorted(av_n), f"iter G[{u}]")
    eq(dict(av_f), dict(av_n), f"dict(G[{u}])")
    eq(sorted(av_f.keys()), sorted(av_n.keys()), f"keys G[{u}]")
    eq(av_f.copy(), av_n.copy(), f"copy G[{u}]")
    eq(av_f == dict(av_n), True, f"eq-dict G[{u}]")
    eq(bool(av_f), bool(av_n), f"bool G[{u}]")
    for v in [1,2,5,7,9]:
        eq(v in av_f, v in av_n, f"{v} in G[{u}]")
        eq(av_f.get(v, "D"), av_n.get(v, "D") if not isinstance(av_n.get(v),dict) else av_f.get(v), f"get G[{u}][{v}]")
# single-edge lookup value
eq(Gf[0][1], Gn[0][1], "G[0][1] value")
# items
eq(sorted((str(k),sorted(d.items())) for k,d in Gf[2].items()),
   sorted((str(k),sorted(d.items())) for k,d in Gn[2].items()), "items G[2]")
# MUTATION through G[u][v] persists + reflects in edges
Gf[0][1]['weight']=99; Gn[0][1]['weight']=99
eq(Gf[0][1]['weight'], 99, "mutate G[0][1] persists")
eq(dict(Gf.edges[0,1]), dict(Gn.edges[0,1]), "edges[0,1] after G[u][v] mutate")
# LIVE view: add edge after taking G[u], view reflects it (nx semantics)
avf = Gf[0]; avn = Gn[0]
Gf.add_edge(0,7); Gn.add_edge(0,7)
eq(7 in avf, 7 in avn, "live: 7 in G[0] after add_edge")
eq(len(avf), len(avn), "live: len after add_edge")
# KeyError on non-neighbor
try: Gf[0][3]; ok=False
except KeyError: ok=True
eq(ok, True, "KeyError G[0][3] non-neighbor")
# G[missing] -> KeyError
try: Gf[123]; ok=False
except KeyError: ok=True
eq(ok, True, "KeyError G[missing-node]")
# G.adj[u] == G[u]
eq(dict(Gf.adj[2]), dict(Gf[2]), "G.adj[2]==G[2]")
print(f"\nMISMATCH={mism}")
