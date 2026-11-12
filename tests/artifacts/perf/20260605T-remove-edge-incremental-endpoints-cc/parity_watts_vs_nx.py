import franken_networkx as fnx, networkx as nx, time, hashlib, json
# CORRECTNESS: byte-exact vs nx across seeds/params (edge set + adjacency order)
def graph_sig(G):
    # exact edge list in G.edges() order + node order
    nodes=list(G.nodes())
    edges=[(u,v) for u,v in G.edges()]
    return json.dumps({"n":nodes,"e":edges},default=str)
mism=0; sigs=[]
for n in [20,50,100,200]:
    for k in [4,6,8]:
        for p in [0.0,0.1,0.3,0.5,1.0]:
            for seed in [1,2,7,42]:
                gf=fnx.watts_strogatz_graph(n,k,p,seed=seed)
                gn=nx.watts_strogatz_graph(n,k,p,seed=seed)
                sf=graph_sig(gf); sn=graph_sig(gn)
                if sf!=sn:
                    mism+=1
                    if mism<=3: print(f"MISMATCH n{n} k{k} p{p} seed{seed}")
                sigs.append(sf)
print(f"watts CASES={len(sigs)} MISMATCH={mism}")
print("GOLDEN_SHA256", hashlib.sha256("\n".join(sigs).encode()).hexdigest())
# also newman + connected_watts (also use remove? newman doesn't, but verify no regression)
m2=0
for n in [50,100]:
    for seed in [1,5]:
        if fnx.watts_strogatz_graph(n,6,0.2,seed=seed).number_of_edges()!=nx.watts_strogatz_graph(n,6,0.2,seed=seed).number_of_edges(): m2+=1
print("edgecount spotcheck mism:", m2)
