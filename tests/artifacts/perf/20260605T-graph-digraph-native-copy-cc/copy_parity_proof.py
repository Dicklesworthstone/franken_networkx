import random
import networkx as nx, franken_networkx as fnx
def build(seed, directed, sl):
    rng=random.Random(seed); n=rng.randint(4,15)
    base=nx.gnp_random_graph(n, 0.3, seed=seed, directed=directed)
    Gn=(nx.DiGraph if directed else nx.Graph)(); Gf=(fnx.DiGraph if directed else fnx.Graph)()
    Gn.add_nodes_from(base.nodes()); Gf.add_nodes_from(base.nodes())
    es=list(base.edges())
    if sl:
        for x in list(base.nodes())[:2]: es.append((x,x))
    for u,v in es:
        w=rng.randint(1,9); Gn.add_edge(u,v,weight=w); Gf.add_edge(u,v,weight=w)
    for x in list(base.nodes())[:3]: Gn.nodes[x]['c']=str(x); Gf.nodes[x]['c']=str(x)
    Gn.graph['gk']='gv'; Gf.graph['gk']='gv'
    return Gf,Gn
def sig(G):
    return (list(G.nodes()),
            [(u,v,tuple(sorted(d.items()))) for u,v,d in G.edges(data=True)],
            sorted(G.graph.items()),
            [(x,tuple(sorted(G.nodes[x].items()))) for x in G.nodes()])
mism=0; cases=0
for seed in range(400):
    for directed in (0,1):
        for sl in (0,1):
            Gf,Gn=build(seed,directed,sl)
            Cf=Gf.copy(); Cn=Gn.copy()
            if sig(Cf)!=sig(Cn): mism+=1; (print('COPY DIFF',seed,directed,sl) if mism<=4 else None); cases+=1; continue
            # copy must equal original
            if sig(Cf)!=sig(Gf): mism+=1; print('copy!=orig',seed)
            # independence: mutate copy, original unchanged
            of=sig(Gf)
            Cf.add_node('ZZZ'); 
            if 'ZZZ' in Gf: mism+=1; print('not independent',seed)
            # shallow attr sharing parity: nx copy shares nested? skip (covered by intentional-divergences)
            cases+=1
print(f"copy parity: cases={cases} mismatches={mism}")
