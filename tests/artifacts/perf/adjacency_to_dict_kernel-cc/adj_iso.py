import franken_networkx as fnx, hashlib, sys
tag=sys.argv[1]
import random
sigs=[]
for kind in ["g","d"]:
    for seed in range(8):
        r=random.Random(seed)
        G=(fnx.DiGraph if kind=="d" else fnx.Graph)()
        G.add_nodes_from(range(40))
        for _ in range(80):
            a,b=r.randrange(40),r.randrange(40)
            if a!=b: G.add_edge(a,b)
        if seed%2:
            for e in list(G.edges())[:30]: G[e[0]][e[1]]['w']=r.randint(1,9)
        adj_f=dict(G.adjacency())
        sigs.append(repr([(k, list(adj_f[k].items())) for k in adj_f]))
print(f"[{tag}] fnx-own adjacency sha:", hashlib.sha256("|".join(sigs).encode()).hexdigest()[:16])
