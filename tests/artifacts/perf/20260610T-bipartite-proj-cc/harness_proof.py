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
    edges=sorted(tuple(sorted((repr(u),repr(v)))) for u,v in G.edges())
    return json.dumps([nodes, edges, sorted((repr(k),repr(v)) for k,v in G.graph.items())])
fh=hashlib.sha256(); nh=hashlib.sha256(); mism=0; total=0
for seed in range(10):
    bn=nx.bipartite.random_graph(40,30,0.1,seed=seed); bf=mkbf(bn)
    top=[n for n,d in bn.nodes(data=True) if d['bipartite']==0]
    bot=[n for n,d in bn.nodes(data=True) if d['bipartite']==1]
    for ns in (top,bot):
        total+=1; a=fp(nxbp.projected_graph(bn,ns)); b=fp(fbp.projected_graph(bf,ns))
        if a!=b: mism+=1; print(f"MISMATCH seed{seed}") if mism<=2 else None
        nh.update(a.encode()); fh.update(b.encode())
# string-labeled bipartite + self-contained
bn=nx.Graph(); bn.add_nodes_from(["a","b","c"],bipartite=0); bn.add_nodes_from(["x","y"],bipartite=1)
bn.add_edges_from([("a","x"),("b","x"),("b","y"),("c","y")]); bf=mkbf(bn)
total+=1; a=fp(nxbp.projected_graph(bn,["a","b","c"])); b=fp(fbp.projected_graph(bf,["a","b","c"]))
if a!=b: mism+=1; print("STR MISMATCH")
nh.update(a.encode()); fh.update(b.encode())
# empty projection set, single node
bn=nx.bipartite.random_graph(5,4,0.3,seed=2); bf=mkbf(bn)
top=[n for n,d in bn.nodes(data=True) if d['bipartite']==0]
total+=1; a=fp(nxbp.projected_graph(bn,top[:1])); b=fp(fbp.projected_graph(bf,top[:1]))
if a!=b: mism+=1; print("SINGLE MISMATCH")
nh.update(a.encode()); fh.update(b.encode())
print(f"cases={total} mismatches={mism}")
print(f"fnx_sha={fh.hexdigest()}\nnx_sha ={nh.hexdigest()}\nMATCH={fh.hexdigest()==nh.hexdigest()}")
