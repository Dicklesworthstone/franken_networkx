import franken_networkx as fnx, networkx as nx, random
mism=0; total=0
def build_pair(kind,seed):
    r=random.Random(seed)
    n=50
    edges=[]
    while len(edges)< (100 if kind!="multi" else 90):
        a,b=r.randrange(n),r.randrange(n)
        if a!=b or kind in("multi","multidi"): edges.append((a,b,{'w':r.randint(1,9)}))
    cls_nx={"simple":nx.Graph,"directed":nx.DiGraph,"multi":nx.MultiGraph,"multidi":nx.MultiDiGraph}[kind]
    cls_f={"simple":fnx.Graph,"directed":fnx.DiGraph,"multi":fnx.MultiGraph,"multidi":fnx.MultiDiGraph}[kind]
    G=cls_nx(); G.add_nodes_from(range(n)); G.add_edges_from(edges)
    Gf=cls_f(); Gf.add_nodes_from(range(n)); Gf.add_edges_from(edges)
    return G,Gf,r,n
for kind in ["simple","directed","multi","multidi"]:
    for seed in range(8):
        G,Gf,r,n=build_pair(kind,seed)
        S=set(r.sample(range(n),n//2))
        S2=set(r.sample([x for x in range(n) if x not in S],n//4))
        for nb2 in [None,S2,set()]:
            for data in [False,True,'w','missing']:
                for default in [None,-1]:
                    ex=list(nx.edge_boundary(G,S,nb2,data=data,default=default))
                    fx=list(fnx.edge_boundary(Gf,S,nb2,data=data,default=default))
                    total+=1
                    if ex!=fx:
                        mism+=1
                        if mism<=5: print(f"MISMATCH {kind} s{seed} nb2={'set' if nb2 is not None else None} data={data} def={default}: lens {len(ex)},{len(fx)}")
print(f"total {total} mismatches {mism}")
