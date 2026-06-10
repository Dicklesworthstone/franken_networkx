import warnings, hashlib, json, os; warnings.filterwarnings("ignore")
os.environ["NETWORKX_AUTOMATIC_BACKENDS"]=""
import networkx as nx, franken_networkx as fnx
import franken_networkx.bipartite as fbp
import networkx.algorithms.bipartite as nxbp
try: nx.config.backend_priority=[]
except Exception: pass
def mkbf(bn):
    bf=fnx.Graph(); bf.graph.update(bn.graph); bf.add_nodes_from(bn.nodes(data=True)); bf.add_edges_from(bn.edges(data=True)); return bf
def fp(G):
    nodes=sorted((repr(n), tuple(sorted(d.items()))) for n,d in G.nodes(data=True))
    edges=sorted((tuple(sorted((repr(u),repr(v)))), round(d.get("weight"),12) if isinstance(d.get("weight"),float) else d.get("weight")) for u,v,d in G.edges(data=True))
    return json.dumps([nodes, edges])
variants=[
    ("weighted", lambda B,n: fbp.weighted_projected_graph(B,n), lambda B,n: nxbp.weighted_projected_graph(B,n)),
    ("weighted_ratio", lambda B,n: fbp.weighted_projected_graph(B,n,ratio=True), lambda B,n: nxbp.weighted_projected_graph(B,n,ratio=True)),
    ("overlap_jac", lambda B,n: fbp.overlap_weighted_projected_graph(B,n), lambda B,n: nxbp.overlap_weighted_projected_graph(B,n)),
    ("overlap_ovl", lambda B,n: fbp.overlap_weighted_projected_graph(B,n,jaccard=False), lambda B,n: nxbp.overlap_weighted_projected_graph(B,n,jaccard=False)),
    ("generic", lambda B,n: fbp.generic_weighted_projected_graph(B,n), lambda B,n: nxbp.generic_weighted_projected_graph(B,n)),
    ("collab", lambda B,n: fbp.collaboration_weighted_projected_graph(B,n), lambda B,n: nxbp.collaboration_weighted_projected_graph(B,n)),
]
fh=hashlib.sha256(); nh=hashlib.sha256(); mism=0; total=0
graphs=[]
for seed in range(8):
    bn=nx.bipartite.random_graph(40,30,0.12,seed=seed); graphs.append((bn, [n for n,d in bn.nodes(data=True) if d['bipartite']==0]))
# string-labeled + degree-1 bottom nodes (collab edge case deg>1)
bn=nx.Graph(); bn.add_nodes_from(["a","b","c"],bipartite=0); bn.add_nodes_from(["x","y","z"],bipartite=1)
bn.add_edges_from([("a","x"),("b","x"),("b","y"),("c","y"),("a","z")]); graphs.append((bn,["a","b","c"]))
for bn,top in graphs:
    bf=mkbf(bn)
    for name,ff,nf in variants:
        try:
            a=fp(nf(bn,top)); b=fp(ff(bf,top))
        except Exception as e:
            print(f"ERR {name}: {e}"); continue
        total+=1
        if a!=b:
            mism+=1
            if mism<=4: print(f"MISMATCH {name}: {a[:120]} vs {b[:120]}")
        nh.update((name+a).encode()); fh.update((name+b).encode())
print(f"cases={total} mismatches={mism}")
print(f"fnx_sha={fh.hexdigest()}\nnx_sha ={nh.hexdigest()}\nMATCH={fh.hexdigest()==nh.hexdigest()}")
