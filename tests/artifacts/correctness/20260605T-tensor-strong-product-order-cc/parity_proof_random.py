import random
import networkx as nx, franken_networkx as fnx
def build(kind, n, p, seed, selfloops=False):
    directed = kind in ('d','md'); multi = kind in ('m','md')
    nc={'u':(nx.Graph,fnx.Graph),'d':(nx.DiGraph,fnx.DiGraph),'m':(nx.MultiGraph,fnx.MultiGraph),'md':(nx.MultiDiGraph,fnx.MultiDiGraph)}[kind]
    base=nx.gnp_random_graph(n,p,seed=seed,directed=directed)
    Gn=nc[0](); Gf=nc[1](); Gn.add_nodes_from(base.nodes()); Gf.add_nodes_from(base.nodes())
    rng=random.Random(seed)
    es=list(base.edges())
    if selfloops:
        for x in list(base.nodes())[:2]: es.append((x,x))
    for u,v in es:
        w=rng.randint(0,5); Gn.add_edge(u,v,weight=w); Gf.add_edge(u,v,weight=w)
        if multi: Gn.add_edge(u,v,weight=w+9); Gf.add_edge(u,v,weight=w+9)
    return Gn,Gf
def sig(G):
    e=[(u,v,k,tuple(sorted(d.items()))) for u,v,k,d in G.edges(keys=True,data=True)] if G.is_multigraph() else [(u,v,tuple(sorted(d.items()))) for u,v,d in G.edges(data=True)]
    return (list(G.nodes()), e)
mism=0; cases=0
for op in ('tensor_product','strong_product'):
    for kind in ('u','d','m','md'):
        for c in range(8):
            sl = c%3==0
            Gn1,Gf1=build(kind,5+c%4,0.4,1000+c,selfloops=sl)
            Gn2,Gf2=build(kind,4+c%3,0.5,2000+c)
            Rn=getattr(nx,op)(Gn1,Gn2); Rf=getattr(fnx,op)(Gf1,Gf2)
            if sig(Rn)!=sig(Rf):
                mism+=1
                if mism<=3: print(f"{op} {kind} c{c} sl{sl} MISMATCH nodes_eq={list(Rn.nodes())==list(Rf.nodes())}")
            cases+=1
print(f"big random: cases={cases} mismatches={mism}")
