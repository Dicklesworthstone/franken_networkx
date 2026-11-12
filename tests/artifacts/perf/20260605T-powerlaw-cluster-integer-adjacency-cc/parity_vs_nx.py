import franken_networkx as fnx, networkx as nx, hashlib, json
def sig(G):
    return json.dumps({"n":list(G.nodes()),"e":[(u,v) for u,v in G.edges()]},default=str)
mism=0; sigs=[]
for n in [20,50,100,200,400]:
    for m in [1,2,3,4,6]:
        if m>=n: continue
        for p in [0.0,0.1,0.3,0.5,0.9,1.0]:
            for seed in [1,2,7,42,123]:
                gf=fnx.powerlaw_cluster_graph(n,m,p,seed=seed)
                gn=nx.powerlaw_cluster_graph(n,m,p,seed=seed)
                sf=sig(gf); sn=sig(gn)
                if sf!=sn:
                    mism+=1
                    if mism<=4: print(f"MISMATCH n{n} m{m} p{p} seed{seed}: edges fnx={gf.number_of_edges()} nx={gn.number_of_edges()}")
                sigs.append(sf)
print(f"powerlaw_cluster CASES={len(sigs)} MISMATCH={mism}")
print("GOLDEN_SHA256", hashlib.sha256("\n".join(sigs).encode()).hexdigest())
