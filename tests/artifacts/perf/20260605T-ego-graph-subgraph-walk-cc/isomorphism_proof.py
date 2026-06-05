import os, hashlib, random, importlib, sys
for v in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']: os.environ[v]='2'
import franken_networkx as fnx

def build(seed, directed, n, p, weighted, selfloops):
    import networkx as nx
    rng = random.Random(seed)
    Gn = nx.gnp_random_graph(n, p, seed=seed, directed=directed)
    F = (fnx.DiGraph if directed else fnx.Graph)()
    F.add_nodes_from(list(Gn.nodes()))
    edges=list(Gn.edges())
    if selfloops:
        for x in list(Gn.nodes())[:max(1,n//7)]:
            if rng.random()<0.5: edges.append((x,x))
    for (u,v) in edges:
        if weighted: F.add_edge(u,v,weight=rng.randint(1,9))
        else: F.add_edge(u,v)
    return F

def sig(H):
    return (list(H.nodes()),
            [(u,v,tuple(sorted(d.items()))) for u,v,d in H.edges(data=True)],
            tuple(sorted(H.graph.items())),
            [(x,tuple(sorted(H.nodes[x].items()))) for x in H.nodes()])

mode = sys.argv[1]  # 'new' or 'old'
sha = hashlib.sha256(); cases=0
for case in range(150):
    directed = case%2==1
    n = 10 + case%30; p = 0.08+(case%5)*0.05
    weighted = case%3==0; selfloops = case%4==0
    F = build(9000+case, directed, n, p, weighted, selfloops)
    for src in list(F.nodes())[:5]:
        for radius in (1,2,3,4):
            for center in (True, False):
                for undirected in ((False,) if not directed else (False,True)):
                    H = fnx.ego_graph(F, src, radius=radius, center=center, undirected=undirected)
                    sha.update(repr(sig(H)).encode()); cases+=1
                    if weighted:
                        H2 = fnx.ego_graph(F, src, radius=radius, center=center, undirected=undirected, distance='weight')
                        sha.update(repr(sig(H2)).encode()); cases+=1
print(f"{mode} cases={cases} sha={sha.hexdigest()}")
