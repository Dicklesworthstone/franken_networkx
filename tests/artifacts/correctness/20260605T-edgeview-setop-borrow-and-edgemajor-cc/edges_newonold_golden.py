import sys, hashlib, random
import franken_networkx as fnx
def build(kind, n, p, seed, selfloops=False, attrs=True):
    directed = kind in ('d','md'); multi = kind in ('m','md')
    cls={'u':fnx.Graph,'d':fnx.DiGraph,'m':fnx.MultiGraph,'md':fnx.MultiDiGraph}[kind]
    import networkx as nx
    base=nx.gnp_random_graph(n,p,seed=seed,directed=directed)
    G=cls(); G.add_nodes_from(base.nodes())
    rng=random.Random(seed); es=list(base.edges())
    if selfloops:
        for x in list(base.nodes())[:2]: es.append((x,x))
    for u,v in es:
        if attrs: G.add_edge(u,v,weight=rng.randint(0,5),tag='e%d'%(u))
        else: G.add_edge(u,v)
        if multi: G.add_edge(u,v,weight=99)
    return G
def sig(G):
    out=[]
    # data=False
    out.append(('E', list(G.edges())))
    # data=True (values)
    if G.is_multigraph():
        out.append(('ED', [(u,v,k,tuple(sorted(d.items()))) for u,v,k,d in G.edges(keys=True,data=True)]))
    else:
        out.append(('ED', [(u,v,tuple(sorted(d.items()))) for u,v,d in G.edges(data=True)]))
        # identity: is d the live G[u][v]?
        ident=[]
        for u,v,d in G.edges(data=True):
            ident.append(d is G[u][v])
        out.append(('IDENT', ident))
    # data='weight'
    out.append(('EW', list(G.edges(data='weight'))))
    out.append(('EWD', list(G.edges(data='weight', default=-1))))
    return out
sha=hashlib.sha256()
for ci,kind in enumerate(['u','d','m','md']):
    for c in range(6):
        for sl in (False,True):
            G=build(kind, 6+c, 0.35, 100+c, selfloops=sl, attrs=(c%2==0))
            s=sig(G); sha.update(repr((kind,c,sl,s)).encode())
print("EDGES_GOLDEN", sha.hexdigest())
