import franken_networkx as fnx, networkx as nx, random, hashlib, json
def sig(G):
    return json.dumps({
        "nodes": list(G.nodes()),
        "edges": sorted(tuple(sorted((str(u),str(v)))) for u,v in G.edges()),
        "edge_order": [(str(u),str(v)) for u,v in G.edges()],
        "edata": sorted((str(u),str(v),sorted(d.items())) for u,v,d in G.edges(data=True)),
        "deg": sorted((str(n),G.degree(n)) for n in G.nodes()),
    }, default=str)
mism=0; sigs=[]
rng=random.Random(11)
for trial in range(40):
    n=rng.randint(5,40); m=rng.randint(0,n*3)
    es=[]
    for _ in range(m):
        u=rng.randrange(n); v=rng.randrange(n)
        es.append((u,v))
    Gf=fnx.Graph(); Gn=nx.Graph(); Gf.add_nodes_from(range(n)); Gn.add_nodes_from(range(n))
    for u,v in es:
        w=rng.random(); Gf.add_edge(u,v,weight=w); Gn.add_edge(u,v,weight=w)
    # remove a random subset of nodes one at a time
    to_remove=rng.sample(range(n), k=rng.randint(0,n))
    for x in to_remove:
        Gf.remove_node(x); Gn.remove_node(x)
    sf, sn = sig(Gf), sig(Gn)
    if sf!=sn:
        mism+=1
        if mism<=3:
            print(f"MISMATCH trial {trial} n={n} removed={to_remove[:5]}...")
            if json.loads(sf)['nodes']!=json.loads(sn)['nodes']: print("  node order differs")
            if json.loads(sf)['edge_order']!=json.loads(sn)['edge_order']: print("  edge order differs")
    sigs.append(sf)
    # native algos must still work on the mutated graph (CSR adj_indices correct)
    if len(Gf)>2:
        try:
            tf=fnx.triangles(Gf); tn=nx.triangles(Gn)
            if {str(k):v for k,v in tf.items()}!={str(k):v for k,v in tn.items()}: mism+=1; print(f"  triangles mismatch trial {trial}")
        except Exception as e: mism+=1; print(f"  native algo error trial {trial}: {e}")
print(f"\nTRIALS={len(sigs)} MISMATCH={mism}")
print("GOLDEN_SHA256", hashlib.sha256("\n".join(sigs).encode()).hexdigest())
