import networkx as nx, franken_networkx as fnx
from franken_networkx._fnx import all_shortest_paths as raw
mism=0; cases=0
for case in range(150):
    n=8+case%22; p=0.10+(case%5)*0.04
    G=nx.gnp_random_graph(n,p,seed=33000+case,directed=True)
    F=fnx.DiGraph(); F.add_nodes_from(G.nodes()); F.add_edges_from(G.edges())
    nodes=list(G.nodes())
    for s in nodes[:6]:
        for t in nodes[:6]:
            try: gn=list(nx.all_shortest_paths(G,s,t))
            except nx.NetworkXNoPath: continue
            except nx.NodeNotFound: continue
            gf=raw(F,s,t,method='unweighted')
            if gf!=gn:
                mism+=1
                if mism<=5: print(f"MISMATCH case={case} s={s} t={t}\n nx={gn}\n fx={gf}")
            cases+=1
print(f"directed raw-kernel cases={cases} mismatches={mism}")
