import franken_networkx as fnx, networkx as nx, random
mism=0
def eq(a,b,label):
    global mism
    if a!=b: mism+=1; print(f"MISMATCH {label}: fnx={a!r} nx={b!r}")
rng=random.Random(7)
Gf=fnx.DiGraph(); Gn=nx.DiGraph()
for u,v in [(0,1),(1,2),(2,0),(0,3),(3,4),(4,0),(2,5),(0,0)]:  # incl self-loop
    w=rng.random(); Gf.add_edge(u,v,weight=w,c='x'); Gn.add_edge(u,v,weight=w,c='x')
Gf.add_node(9); Gn.add_node(9)
for u in [0,1,2,3,4,5,9]:
    af,an=Gf[u],Gn[u]
    eq(len(af),len(an),f"len G[{u}] (succ)")
    eq(sorted(af),sorted(an),f"iter G[{u}]")
    eq(dict(af),dict(an),f"dict(G[{u}])")
    eq(sorted(af.keys()),sorted(an.keys()),f"keys G[{u}]")
    eq(af.copy(),an.copy(),f"copy G[{u}]")
    eq(af==dict(an),True,f"eq G[{u}]")
    eq(bool(af),bool(an),f"bool G[{u}]")
    for v in [0,1,2,4,9]:
        eq(v in af, v in an, f"{v} in G[{u}]")
    # succ / pred views
    eq(dict(Gf.succ[u]),dict(Gn.succ[u]),f"succ[{u}]")
    eq(dict(Gf.pred[u]),dict(Gn.pred[u]),f"pred[{u}]")
    for v in [0,1,2,4]:
        eq(v in Gf.pred[u], v in Gn.pred[u], f"{v} in pred[{u}]")
# directed value + asymmetry: 0->1 exists, 1->0 may not
eq(Gf[0][1], Gn[0][1], "G[0][1] value")
try: Gf[1][0]; ok1=False
except KeyError: ok1=True
eq(ok1, (1 not in Gn[0]) or (0 not in Gn[1]) , "directed KeyError consistency")  # just ensure no crash
# G[u][v] points to OUT edge, not in
eq(2 in Gf[0], 2 in Gn[0], "succ direction 2 in G[0]")
eq(0 in Gf.pred[2], 0 in Gn.pred[2], "pred direction 0 in pred[2]")
# mutation through G[u][v]
Gf[0][1]['weight']=42; Gn[0][1]['weight']=42
eq(Gf[0][1]['weight'],42,"mutate persists")
eq(dict(Gf.edges[0,1]),dict(Gn.edges[0,1]),"edges[0,1] after mutate")
# LIVE view
af=Gf[0]; an=Gn[0]
Gf.add_edge(0,7); Gn.add_edge(0,7)
eq(7 in af, 7 in an, "live: 7 in G[0]")
eq(len(af),len(an),"live len")
# self-loop: 0 in G[0] (0->0 edge)
eq(0 in Gf[0], 0 in Gn[0], "self-loop 0 in G[0]")
# KeyError missing node
try: Gf[123]; ok=False
except KeyError: ok=True
eq(ok,True,"KeyError missing node")
# G.adj[u] == G[u]
eq(dict(Gf.adj[0]),dict(Gf[0]),"adj[0]==G[0]")
print(f"\nMISMATCH={mism}")
