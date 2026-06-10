import warnings, hashlib, json, os; warnings.filterwarnings("ignore")
os.environ["NETWORKX_AUTOMATIC_BACKENDS"]=""
import networkx as nx, franken_networkx as fnx
try: nx.config.backend_priority=[]
except Exception: pass
def fp(G):
    nodes=sorted((repr(n), tuple(sorted(d.items()))) for n,d in G.nodes(data=True))
    edges=sorted((tuple(sorted((repr(u),repr(v)))), tuple(sorted(d.items()))) for u,v,d in G.edges(data=True))
    return json.dumps([nodes, edges])
fh=hashlib.sha256(); nh=hashlib.sha256(); mism=0; total=0
graphs=[]
for seed in range(6):
    gn=nx.gnp_random_graph(30,0.15,seed=seed); graphs.append(gn)
graphs.append(nx.cycle_graph(12)); graphs.append(nx.complete_graph(5)); graphs.append(nx.path_graph(8))
# string-labeled (convert_node_labels_to_integers relabels)
sg=nx.Graph([("a","b"),("b","c"),("c","a"),("c","d")]); graphs.append(sg)
# with edge + node attrs
ag=nx.Graph(); ag.add_node(0,c="x"); ag.add_edge(0,1,w=5); ag.add_edge(1,2,w=7); graphs.append(ag)
graphs.append(nx.empty_graph(4))
for gn in graphs:
    gf=fnx.Graph(); gf.add_nodes_from(gn.nodes(data=True)); gf.add_edges_from(gn.edges(data=True))
    for it in (1,2):
        a=fp(nx.mycielskian(gn,it)); b=fp(fnx.mycielskian(gf,it))
        total+=1
        if a!=b:
            mism+=1
            if mism<=3: print(f"MISMATCH it={it}: {a[:100]} vs {b[:100]}")
        nh.update(a.encode()); fh.update(b.encode())
# edge-attr identity + mutation
gf=fnx.Graph(); gf.add_edge(0,1,w=5); gf.add_edge(1,2,w=7)
r=fnx.mycielskian(gf)
e=list(r.edges())[0]; assert r[e[0]][e[1]] is r[e[0]][e[1]]; r[e[0]][e[1]]["z"]=1
print(f"cases={total} mismatches={mism}")
print(f"fnx_sha={fh.hexdigest()}\nnx_sha ={nh.hexdigest()}\nMATCH={fh.hexdigest()==nh.hexdigest()}")
