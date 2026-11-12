import warnings, hashlib, json, random; warnings.filterwarnings("ignore")
import networkx as nx, franken_networkx as fnx

def cases():
    out=[]
    for seed in range(6):
        gn=nx.gnp_random_graph(100,0.05,seed=seed); gf=fnx.gnp_random_graph(100,0.05,seed=seed)
        r=random.Random(seed); S=r.sample(list(gn),30)
        out.append((f"gnp{seed}.noS2", gn, gf, S, None))
        S2=r.sample(list(gn),40)
        out.append((f"gnp{seed}.S2", gn, gf, S, S2))
    # disconnected + isolated
    gn=nx.Graph([(0,1),(1,2),(5,6),(8,9)]); gn.add_nodes_from([20,21])
    gf=fnx.Graph([(0,1),(1,2),(5,6),(8,9)]); gf.add_nodes_from([20,21])
    out.append(("disc", gn, gf, [0,1,5], None))
    out.append(("disc.iso", gn, gf, [20], None))
    # string labels + self loop
    gn=nx.Graph([("a","b"),("b","c"),("c","c"),("d","e")]); gf=fnx.Graph([("a","b"),("b","c"),("c","c"),("d","e")])
    out.append(("str", gn, gf, ["a","b"], None))
    out.append(("str.S2", gn, gf, ["a"], ["c","e"]))
    # empty S, dup nodes in S, S = all
    out.append(("emptyS", gn, gf, [], None))
    out.append(("dupS", gn, gf, ["a","a","b"], None))
    out.append(("allS", gn, gf, ["a","b","c","d","e"], None))
    return out

fh=hashlib.sha256(); nh=hashlib.sha256(); mism=0; total=0
for name,gn,gf,S,S2 in cases():
    rn=nx.node_boundary(gn,S,S2); rf=fnx.node_boundary(gf,S,S2)
    total+=1
    assert isinstance(rf,set), f"{name} not set"
    if rn!=rf:
        mism+=1
        if mism<=3: print(f"MISMATCH {name}: nx={sorted(map(str,rn))} fnx={sorted(map(str,rf))}")
    fh.update(json.dumps(sorted(map(str,rf))).encode()); fh.update(b"|")
    nh.update(json.dumps(sorted(map(str,rn))).encode()); nh.update(b"|")
print(f"cases={total} mismatches={mism}")
print(f"fnx_sha={fh.hexdigest()}")
print(f"nx_sha ={nh.hexdigest()}")
print(f"MATCH={fh.hexdigest()==nh.hexdigest()}")
