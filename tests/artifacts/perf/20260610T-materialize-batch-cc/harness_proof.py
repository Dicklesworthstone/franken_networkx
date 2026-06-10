import warnings, hashlib, json, os; warnings.filterwarnings("ignore")
os.environ["NETWORKX_AUTOMATIC_BACKENDS"]=""
import networkx as nx, franken_networkx as fnx
from franken_networkx import _materialize_filtered_view
try: nx.config.backend_priority=[]
except Exception: pass
def fp(G):
    nodes=sorted((repr(n), tuple(sorted(d.items()))) for n,d in G.nodes(data=True))
    if G.is_multigraph():
        edges=sorted((repr(u),repr(v),repr(k),tuple(sorted(d.items()))) for u,v,k,d in G.edges(keys=True,data=True))
    else:
        edges=sorted((tuple(sorted((repr(u),repr(v)))),tuple(sorted(d.items()))) for u,v,d in G.edges(data=True))
    return json.dumps([nodes, edges, sorted((repr(k),repr(v)) for k,v in G.graph.items()), G.is_directed(), G.is_multigraph()])
# Compare NEW materialize vs a reference (build from view via edges) — since this is
# internal, compare structure to the VIEW it materializes (must be identical).
def viewfp(view):
    return fp(view)  # view exposes same nodes/edges/attrs
fh=hashlib.sha256(); mism=0; total=0
def mk(cls_dir, cls_multi):
    G = fnx.Graph()
    if cls_dir and cls_multi: G=fnx.MultiDiGraph()
    elif cls_dir: G=fnx.DiGraph()
    elif cls_multi: G=fnx.MultiGraph()
    return G
import random
for seed in range(5):
    for directed in (False,True):
        for multi in (False,True):
            G = mk(directed,multi); G.graph["lbl"]=f"g{seed}"
            r=random.Random(seed)
            n=40
            for i in range(n): G.add_node(i, c=i%3)
            for _ in range(120):
                u,v=r.randrange(n),r.randrange(n)
                if u!=v: G.add_edge(u,v,w=r.randint(1,5))
            sub=r.sample(range(n),28)
            view=G.subgraph(sub)
            try: view.__dict__.pop("_fnx_materialized_cache",None)
            except Exception: pass
            mat=_materialize_filtered_view(view)
            total+=1
            a=viewfp(view); b=fp(mat)
            if a!=b:
                mism+=1
                if mism<=3: print(f"MISMATCH dir={directed} multi={multi} seed{seed}")
            fh.update(b.encode())
# edge_subgraph view + attr identity
G=fnx.Graph(); 
for u,v in [(0,1),(1,2),(2,3),(0,3),(1,3)]: G.add_edge(u,v,w=u+v)
ev=G.edge_subgraph([(0,1),(1,2),(2,3)])
try: ev.__dict__.pop("_fnx_materialized_cache",None)
except Exception: pass
mat=_materialize_filtered_view(ev)
total+=1
if fp(ev)!=fp(mat): mism+=1; print("EDGE-SUB MISMATCH")
e=list(mat.edges())[0]; assert mat[e[0]][e[1]] is mat[e[0]][e[1]]; mat[e[0]][e[1]]["z"]=1
fh.update(fp(mat).encode())
print(f"cases={total} mismatches={mism}")
print(f"sha={fh.hexdigest()}")
