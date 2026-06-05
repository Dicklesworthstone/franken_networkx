import franken_networkx as fnx, networkx as nx, random, hashlib, json
mism=0; cases=0; sigs=[]
# Broad reciprocal + remove sweep
for seed in range(200):
    rng=random.Random(seed); n=rng.randint(3,14)
    Gf=fnx.DiGraph(); Gn=nx.DiGraph(); Gf.add_nodes_from(range(n)); Gn.add_nodes_from(range(n))
    for _ in range(rng.randint(2,28)):
        u=rng.randrange(n); v=rng.randrange(n)
        # vary attrs: sometimes extra keys to exercise dict.update merge
        d={'weight':rng.randint(1,99)}
        if rng.random()<0.3: d['lbl']=f"x{rng.randint(0,3)}"
        Gf.add_edge(u,v,**d); Gn.add_edge(u,v,**d)
    if n>3 and rng.random()<0.6:
        x=rng.randrange(n); Gf.remove_node(x); Gn.remove_node(x)
    cases+=1
    uf=Gf.to_undirected(); un=Gn.to_undirected()
    sf=([(str(a),str(b)) for a,b in uf.edges()],
        sorted((tuple(sorted((str(a),str(b)))), sorted((k,str(v)) for k,v in d.items())) for a,b,d in uf.edges(data=True)),
        list(map(str,uf.nodes())))
    sn=([(str(a),str(b)) for a,b in un.edges()],
        sorted((tuple(sorted((str(a),str(b)))), sorted((k,str(v)) for k,v in d.items())) for a,b,d in un.edges(data=True)),
        list(map(str,un.nodes())))
    if sf!=sn:
        mism+=1
        if mism<=4:
            d2=[i for i in range(len(sf[1])) if i<len(sn[1]) and sf[1][i]!=sn[1][i]]
            print(f"seed{seed}: order_eq={sf[0]==sn[0]} attr_diff_idx={d2[:2]}")
    sigs.append(json.dumps(sf,default=str))
print(f"to_undirected: CASES={cases} MISMATCH={mism}")
# determinism: same graph twice -> identical to_undirected
g=fnx.DiGraph(); 
for u,v,w in [(0,1,1),(1,0,2),(2,1,3),(1,2,4),(0,2,5),(2,0,6)]: g.add_edge(u,v,weight=w)
g.remove_node(1)
r1=[(u,v,d.get('weight')) for u,v,d in g.to_undirected().edges(data=True)]
r2=[(u,v,d.get('weight')) for u,v,d in g.to_undirected().edges(data=True)]
print("determinism (2 calls identical):", r1==r2)
print("GOLDEN_SHA256", hashlib.sha256("\n".join(sigs).encode()).hexdigest())
