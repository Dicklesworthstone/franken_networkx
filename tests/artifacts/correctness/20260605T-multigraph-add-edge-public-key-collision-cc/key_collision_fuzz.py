"""Reproducer: MultiGraph.add_edge auto-key returns a COLLIDING key after
subgraph/copy + mixed int/str key sequences, overwriting/duplicating an edge.
fnx returns key=1 (collides with existing (3,2,1)) where nx returns key=2."""
import random
import networkx as nx, franken_networkx as fnx
def run(seed, directed):
    rng=random.Random(seed)
    Gf=(fnx.MultiDiGraph if directed else fnx.MultiGraph)(); Gn=(nx.MultiDiGraph if directed else nx.MultiGraph)()
    for _ in range(45):
        op=rng.random(); a=rng.randrange(5); b=rng.randrange(5)
        if op<0.30:
            w=rng.randint(1,4); kf=Gf.add_edge(a,b,weight=w); kn=Gn.add_edge(a,b,weight=w)
            if kf!=kn: return (seed,directed,a,b,kf,kn)
        elif op<0.42:
            kk=rng.choice(['x',0,1,'k2']); Gf.add_edge(a,b,key=kk,c=1); Gn.add_edge(a,b,key=kk,c=1)
        elif op<0.52:
            ks=list(Gn[a][b]) if (a in Gn and b in Gn[a]) else []
            if ks: kk=ks[0]; Gn.remove_edge(a,b,kk); Gf.remove_edge(a,b,kk)
        elif op<0.60:
            if Gn.has_edge(a,b): Gn.remove_edge(a,b); Gf.remove_edge(a,b)
        elif op<0.74:
            if op>=0.68: Gf.clear_edges(); Gn.clear_edges()
        elif op<0.80:
            if a in Gn: Gn.remove_node(a); Gf.remove_node(a)
        elif op<0.88: Gf=Gf.copy(); Gn=Gn.copy()
        elif op<0.94:
            sub=[x for x in range(5) if rng.random()<0.6]; Gf=Gf.subgraph([x for x in sub if x in Gf]).copy(); Gn=Gn.subgraph([x for x in sub if x in Gn]).copy()
        else: Gf.add_node(a,tag=str(a)); Gn.add_node(a,tag=str(a))
    return None
hits=[run(s,0) for s in range(50)]; hits=[h for h in hits if h]
print('first diverging seeds (seed,dir,u,v,fnx_key,nx_key):', hits[:3])
