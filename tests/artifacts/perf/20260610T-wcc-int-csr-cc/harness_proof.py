import warnings, hashlib, json; warnings.filterwarnings("ignore")
import networkx as nx, franken_networkx as fnx

def cases():
    out=[]
    for seed in range(6):
        out.append(("gnp_di", nx.gnp_random_graph(80,0.03,seed=seed,directed=True), fnx.gnp_random_graph(80,0.03,seed=seed,directed=True)))
    # multi-component + isolated
    gn=nx.DiGraph([(0,1),(1,2),(5,6),(6,5),(8,9)]); gn.add_nodes_from([20,21,22])
    gf=fnx.DiGraph([(0,1),(1,2),(5,6),(6,5),(8,9)]); gf.add_nodes_from([20,21,22])
    out.append(("multicomp", gn, gf))
    # string labels + self loops
    gn=nx.DiGraph([("a","b"),("b","a"),("c","c"),("d","e")]); gn.add_node("z")
    gf=fnx.DiGraph([("a","b"),("b","a"),("c","c"),("d","e")]); gf.add_node("z")
    out.append(("strlabel", gn, gf))
    # MultiDiGraph
    mn=nx.MultiDiGraph([(0,1),(0,1),(1,0),(2,3),(4,4)])
    mf=fnx.MultiDiGraph([(0,1),(0,1),(1,0),(2,3),(4,4)])
    out.append(("multidi", mn, mf))
    # empty + single
    out.append(("empty", nx.DiGraph(), fnx.DiGraph()))
    sn=nx.DiGraph(); sn.add_node(7); sf=fnx.DiGraph(); sf.add_node(7)
    out.append(("single", sn, sf))
    return out

fh=hashlib.sha256(); nh=hashlib.sha256()
set_mism=0; order_mism=0; total=0
for name,gn,gf in cases():
    rn=[set(c) for c in nx.weakly_connected_components(gn)]
    rf=[set(c) for c in fnx.weakly_connected_components(gf)]
    total+=1
    # set-of-frozensets equality (contract)
    if {frozenset(c) for c in rn} != {frozenset(c) for c in rf}:
        set_mism+=1; print(f"SET MISMATCH {name}")
    # ordered discovery-order equality (stronger)
    if rn != rf:
        order_mism+=1
        if order_mism<=2: print(f"ORDER diff {name}: nx={[sorted(map(str,c)) for c in rn][:3]} fnx={[sorted(map(str,c)) for c in rf][:3]}")
    # golden: sorted-within, discovery-order-preserved fingerprint
    fh.update(json.dumps([sorted(map(str,c)) for c in rf]).encode()); fh.update(b"|")
    nh.update(json.dumps([sorted(map(str,c)) for c in rn]).encode()); nh.update(b"|")
print(f"cases={total} set_mismatches={set_mism} order_mismatches={order_mism}")
print(f"fnx_sha={fh.hexdigest()}")
print(f"nx_sha ={nh.hexdigest()}")
print(f"MATCH(order+contents)={fh.hexdigest()==nh.hexdigest()}")
