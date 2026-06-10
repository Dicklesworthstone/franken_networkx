import warnings, hashlib, json, os; warnings.filterwarnings("ignore")
os.environ["NETWORKX_AUTOMATIC_BACKENDS"]=""
import networkx as nx, franken_networkx as fnx
try: nx.config.backend_priority=[]
except Exception: pass
strategies=["smallest_last","largest_first","connected_sequential_bfs","connected_sequential_dfs","saturation_largest_first","DSATUR","independent_set"]
fh=hashlib.sha256(); nh=hashlib.sha256(); mism=0; total=0
for seed in range(8):
    for n,p in ((60,0.08),(120,0.05)):
        un=nx.gnp_random_graph(n,p,seed=seed); uf=fnx.Graph(); uf.add_nodes_from(un.nodes()); uf.add_edges_from(un.edges())
        for s in strategies:
            a=nx.greedy_color(un,strategy=s); b=fnx.greedy_color(uf,strategy=s)
            total+=1
            if a!=b:
                mism+=1
                if mism<=4: print(f"MISMATCH n={n} seed{seed} {s}: differ at {[k for k in a if a[k]!=b.get(k)][:3]}")
            nh.update((s+json.dumps([(repr(k),v) for k,v in sorted(a.items(),key=lambda x:repr(x[0]))])).encode())
            fh.update((s+json.dumps([(repr(k),v) for k,v in sorted(b.items(),key=lambda x:repr(x[0]))])).encode())
# string labels + interchange + callable fall-through
sg=fnx.Graph([("a","b"),("b","c"),("c","a"),("c","d")]); sgn=nx.Graph([("a","b"),("b","c"),("c","a"),("c","d")])
total+=1
if nx.greedy_color(sgn,strategy="smallest_last")!=fnx.greedy_color(sg,strategy="smallest_last"): mism+=1; print("STR MISMATCH")
nh.update(b"x"); fh.update(b"x")
# interchange path (faithful fallback)
total+=1
if nx.greedy_color(sgn,strategy="largest_first",interchange=True)!=fnx.greedy_color(sg,strategy="largest_first",interchange=True): mism+=1; print("INTERCHANGE MISMATCH")
print(f"cases={total} mismatches={mism}")
print(f"fnx_sha={fh.hexdigest()}\nnx_sha ={nh.hexdigest()}\nMATCH={fh.hexdigest()==nh.hexdigest()}")
