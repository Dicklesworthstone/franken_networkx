import warnings, hashlib, json, os, random; warnings.filterwarnings("ignore")
os.environ["NETWORKX_AUTOMATIC_BACKENDS"]=""
import networkx as nx, franken_networkx as fnx
import networkx.algorithms.approximation as nxa
import franken_networkx.approximation as fa
try: nx.config.backend_priority=[]
except Exception: pass
fh=hashlib.sha256(); nh=hashlib.sha256(); mism=0; total=0
def mkpair(n,p,seed):
    un=nx.gnp_random_graph(n,p,seed=seed); uf=fnx.gnp_random_graph(n,p,seed=seed)
    # NOTE fnx & nx gnp differ (RNG); build uf FROM un for identical structure
    uf=fnx.Graph(); uf.add_nodes_from(un.nodes()); uf.add_edges_from(un.edges())
    return un,uf
for seed in range(6):
    for n,p in ((60,0.08),(100,0.05),(150,0.04)):
        un,uf=mkpair(n,p,seed)
        r=random.Random(seed); nodes=list(un)
        for _ in range(8):
            s=r.choice(nodes); t=r.choice(nodes)
            if s==t: continue
            for cutoff in (None,2):
                a=nxa.local_node_connectivity(un,s,t,cutoff)
                b=fa.local_node_connectivity(uf,s,t,cutoff)
                total+=1
                if a!=b:
                    mism+=1
                    if mism<=4: print(f"MISMATCH n={n} s={s} t={t} cutoff={cutoff}: nx={a} fnx={b}")
                nh.update(str(a).encode()); fh.update(str(b).encode())
# adjacent nodes, degree-0, same-node error, octahedral
oct_n=nx.octahedral_graph(); oct_f=fnx.Graph(); oct_f.add_nodes_from(oct_n.nodes()); oct_f.add_edges_from(oct_n.edges())
for s,t in [(0,5),(0,1)]:
    total+=1; a=nxa.local_node_connectivity(oct_n,s,t); b=fa.local_node_connectivity(oct_f,s,t)
    if a!=b: mism+=1; print(f"OCT MISMATCH {s},{t}: {a} vs {b}")
    nh.update(str(a).encode()); fh.update(str(b).encode())
# same-node raises
try: fa.local_node_connectivity(oct_f,0,0); print("NO RAISE same node")
except Exception as e: pass
print(f"cases={total} mismatches={mism}")
print(f"fnx_sha={fh.hexdigest()}\nnx_sha ={nh.hexdigest()}\nMATCH={fh.hexdigest()==nh.hexdigest()}")
