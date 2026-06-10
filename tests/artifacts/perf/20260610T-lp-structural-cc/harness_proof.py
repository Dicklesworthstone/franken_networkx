import warnings, hashlib, json, os; warnings.filterwarnings("ignore")
os.environ["NETWORKX_AUTOMATIC_BACKENDS"]=""
import networkx as nx, franken_networkx as fnx
from franken_networkx import _networkx_graph_for_parity
try: nx.config.backend_priority=[]
except Exception: pass

# Compare NEW fnx.community.label_propagation_communities vs the FAITHFUL-conversion
# baseline (= nx contract) on the SAME fnx graph, as ORDERED list of community sets.
def baseline(g):
    return [list(c) for c in nx.community.label_propagation_communities(_networkx_graph_for_parity(g))]

fh=hashlib.sha256(); nh=hashlib.sha256(); mism=0; total=0
graphs=[]
for n in (40,100,200):
    for p in (0.03,0.06,0.12):
        for seed in range(4):
            graphs.append(fnx.gnp_random_graph(n,p,seed=seed))
# edge cases
g=fnx.Graph([("a","b"),("b","c"),("c","c"),("a","d")]); g.add_nodes_from(["z","y"]); graphs.append(g)
graphs.append(fnx.Graph([(0,1)]))
graphs.append(fnx.Graph())
graphs.append(fnx.path_graph(20))
graphs.append(fnx.complete_graph(15))
# multigraph (fall-through path)
mg=fnx.MultiGraph([(0,1),(0,1),(1,2),(2,3),(3,1)]); graphs.append(mg)
for g in graphs:
    base=[set(c) for c in baseline(g)] if type(g) is fnx.Graph else [set(c) for c in nx.community.label_propagation_communities(_networkx_graph_for_parity(g))]
    new=[set(c) for c in fnx.community.label_propagation_communities(g)]
    total+=1
    if base!=new:
        mism+=1
        if mism<=3: print(f"MISMATCH type={type(g).__name__} n={g.number_of_nodes()}: same_as_set={set(map(frozenset,base))==set(map(frozenset,new))}")
    bs=json.dumps([sorted(map(str,c)) for c in base]); ns=json.dumps([sorted(map(str,c)) for c in new])
    nh.update(bs.encode()); fh.update(ns.encode())
print(f"cases={total} mismatches={mism}")
print(f"new_sha ={fh.hexdigest()}")
print(f"base_sha={nh.hexdigest()}")
print(f"MATCH={fh.hexdigest()==nh.hexdigest()}")
