import warnings, hashlib, json; warnings.filterwarnings("ignore")
import networkx as nx, franken_networkx as fnx

def cases():
    out=[]
    for seed in range(6):
        gn=nx.gnp_random_graph(120,0.03,seed=seed); gf=fnx.gnp_random_graph(120,0.03,seed=seed)
        for src in (0, 7, 50, 119):
            out.append((f"gnp{seed}.{src}", gn, gf, src))
    # disconnected with isolated + clusters
    gn=nx.Graph([(0,1),(1,2),(5,6),(8,9),(9,10),(10,8)]); gn.add_nodes_from([20,21])
    gf=fnx.Graph([(0,1),(1,2),(5,6),(8,9),(9,10),(10,8)]); gf.add_nodes_from([20,21])
    for src in (0,5,8,20):
        out.append((f"disc.{src}", gn, gf, src))
    # string labels + self loop
    gn=nx.Graph([("a","b"),("b","c"),("c","c"),("d","e")]); gn.add_node("z")
    gf=fnx.Graph([("a","b"),("b","c"),("c","c"),("d","e")]); gf.add_node("z")
    for src in ("a","d","z","c"):
        out.append((f"str.{src}", gn, gf, src))
    return out

fh=hashlib.sha256(); nh=hashlib.sha256(); mism=0; total=0
for name,gn,gf,src in cases():
    rn=nx.node_connected_component(gn,src)
    rf=fnx.node_connected_component(gf,src)
    total+=1
    assert isinstance(rf,set), f"{name}: not a set"
    if rn!=rf:
        mism+=1
        if mism<=3: print(f"MISMATCH {name}: nx={sorted(map(str,rn))} fnx={sorted(map(str,rf))}")
    key=json.dumps(sorted(map(str,rf)))
    fh.update(key.encode()); fh.update(b"|")
    nh.update(json.dumps(sorted(map(str,rn))).encode()); nh.update(b"|")
print(f"cases={total} mismatches={mism}")
print(f"fnx_sha={fh.hexdigest()}")
print(f"nx_sha ={nh.hexdigest()}")
print(f"MATCH={fh.hexdigest()==nh.hexdigest()}")
