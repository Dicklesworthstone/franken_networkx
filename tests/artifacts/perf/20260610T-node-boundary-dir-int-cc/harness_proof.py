import warnings, hashlib, json, random; warnings.filterwarnings("ignore")
import networkx as nx, franken_networkx as fnx

def cases():
    out=[]
    for seed in range(6):
        gn=nx.gnp_random_graph(100,0.05,seed=seed,directed=True); gf=fnx.gnp_random_graph(100,0.05,seed=seed,directed=True)
        r=random.Random(seed); S=r.sample(list(gn),30)
        out.append((f"gnp{seed}.noS2", gn, gf, S, None))
        out.append((f"gnp{seed}.S2", gn, gf, S, r.sample(list(gn),40)))
    gn=nx.DiGraph([(0,1),(1,2),(5,6),(6,5),(8,9)]); gn.add_nodes_from([20,21])
    gf=fnx.DiGraph([(0,1),(1,2),(5,6),(6,5),(8,9)]); gf.add_nodes_from([20,21])
    out.append(("disc", gn, gf, [0,5,8], None))
    out.append(("disc.iso", gn, gf, [20], None))
    gn=nx.DiGraph([("a","b"),("b","c"),("c","c"),("d","e")]); gf=fnx.DiGraph([("a","b"),("b","c"),("c","c"),("d","e")])
    out.append(("str", gn, gf, ["a","b"], None))
    out.append(("str.S2", gn, gf, ["a","b"], ["c","z"]))
    out.append(("emptyS", gn, gf, [], None))
    out.append(("dupS", gn, gf, ["a","a","b"], None))
    out.append(("allS", gn, gf, ["a","b","c","d","e"], None))
    # MultiDiGraph
    mn=nx.MultiDiGraph([(0,1),(0,1),(1,2),(2,0)]); mf=fnx.MultiDiGraph([(0,1),(0,1),(1,2),(2,0)])
    out.append(("multidi", mn, mf, [0], None))
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
