import random
import networkx as nx, franken_networkx as fnx
CLS=[('Graph',fnx.Graph,nx.Graph),('DiGraph',fnx.DiGraph,nx.DiGraph),('MultiGraph',fnx.MultiGraph,nx.MultiGraph),('MultiDiGraph',fnx.MultiDiGraph,nx.MultiDiGraph)]
mism=0; cases=0
for seed in range(400):
    rng=random.Random(seed)
    for name,fcls,ncls in CLS:
        Gf=fcls(); Gn=ncls()
        nodes=rng.sample(range(30), rng.randint(3,15))
        Gf.add_nodes_from(nodes); Gn.add_nodes_from(nodes)
        # node attrs on some
        for n in nodes[:3]: Gf.nodes[n]['c']=str(n); Gn.nodes[n]['c']=str(n)
        for _ in range(rng.randint(2,20)):
            u=rng.choice(nodes); v=rng.choice(nodes)
            w=rng.randint(1,9); Gf.add_edge(u,v,weight=w); Gn.add_edge(u,v,weight=w)
        Gf.graph['g']='x'; Gn.graph['g']='x'
        Gf.clear_edges(); Gn.clear_edges()
        # node order
        if list(Gf.nodes())!=list(Gn.nodes()): mism+=1; (print(f'{name} seed{seed} node-order: fx={list(Gf.nodes())} nx={list(Gn.nodes())}') if mism<=4 else None); cases+=1; continue
        # edges empty
        if list(Gf.edges())!=[] or list(Gn.edges())!=[]: mism+=1; print(f'{name} edges not empty')
        # node attrs preserved
        if [dict(Gf.nodes[n]) for n in Gf.nodes()]!=[dict(Gn.nodes[n]) for n in Gn.nodes()]: mism+=1; print(f'{name} seed{seed} node-attrs lost')
        # graph attrs preserved
        if dict(Gf.graph)!=dict(Gn.graph): mism+=1; print(f'{name} graph attrs')
        # number_of_edges 0
        if Gf.number_of_edges()!=0: mism+=1; print(f'{name} noe!=0')
        # copy after clear preserves node order
        Cf=Gf.copy(); Cn=Gn.copy()
        if list(Cf.nodes())!=list(Cn.nodes()): mism+=1; print(f'{name} seed{seed} copy-after-clear order')
        # can add edges again + multigraph keys work
        Gf.add_edge(nodes[0],nodes[1]); Gn.add_edge(nodes[0],nodes[1])
        if list(Gf.edges())!=list(Gn.edges()): mism+=1; print(f'{name} re-add edge')
        cases+=1
print(f"clear_edges parity: cases={cases} mismatches={mism}")
