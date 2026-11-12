import warnings, hashlib, json, os; warnings.filterwarnings("ignore")
os.environ["NETWORKX_AUTOMATIC_BACKENDS"]=""
import networkx as nx, franken_networkx as fnx
try: nx.config.backend_priority=[]
except Exception: pass

def fp(C):
    parts=["N:"+"|".join(f"{n!r}:{sorted(d.items())!r}" for n,d in C.nodes(data=True))]
    if C.is_directed():
        parts.append("E:"+"|".join(f"{u!r}->{v!r}:{sorted(d.items())!r}" for u,v,d in C.edges(data=True)))
    else:
        parts.append("E:"+"|".join(f"{u!r}-{v!r}:{sorted(d.items())!r}" for u,v,d in C.edges(data=True)))
    parts.append("G:"+repr(sorted(C.graph.items())))
    return "\n".join(parts)

def cases():
    out=[]
    for seed in range(6):
        out.append((f"gnp{seed}", nx.gnp_random_graph(60,0.1,seed=seed), fnx.gnp_random_graph(60,0.1,seed=seed)))
    for seed in range(3):
        out.append((f"di{seed}", nx.gnp_random_graph(50,0.1,seed=seed,directed=True), fnx.gnp_random_graph(50,0.1,seed=seed,directed=True)))
    # with self-loops + node/graph attrs
    gn=nx.Graph([(0,1),(1,2),(0,0)]); gn.add_node(5); gn.nodes[0]["c"]="x"; gn.graph["lbl"]="g"
    gf=fnx.Graph([(0,1),(1,2),(0,0)]); gf.add_node(5); gf.nodes[0]["c"]="x"; gf.graph["lbl"]="g"
    out.append(("attrs", gn, gf))
    # string labels
    out.append(("str", nx.Graph([("a","b"),("b","c")]), fnx.Graph([("a","b"),("b","c")])))
    out.append(("empty", nx.Graph(), fnx.Graph()))
    out.append(("single", nx.Graph([(0,1)]), fnx.Graph([(0,1)])))
    return out

fh=hashlib.sha256(); nh=hashlib.sha256(); mism=0; total=0
for name,gn,gf in cases():
    cn=nx.complement(gn); cf=fnx.complement(gf)
    total+=1
    a=fp(cn); b=fp(cf)
    if a!=b:
        mism+=1
        if mism<=3:
            for x,y in zip(a.split("\n"),b.split("\n")):
                if x!=y: print(f"MISMATCH {name}: nx={x[:90]} fnx={y[:90]}"); break
    # also exercise attr identity + mutation
    if cf.number_of_edges()>0:
        u,v=list(cf.edges())[0]
        assert cf[u][v] is cf[u][v], f"{name}: identity broke"
        cf[u][v]["w"]=1; assert cf[u][v]["w"]==1
    nh.update(a.encode()); fh.update(b.encode())
print(f"cases={total} mismatches={mism}")
print(f"fnx_sha={fh.hexdigest()}")
print(f"nx_sha ={nh.hexdigest()}")
print(f"MATCH={fh.hexdigest()==nh.hexdigest()}")
