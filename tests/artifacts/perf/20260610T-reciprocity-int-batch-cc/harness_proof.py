import warnings, hashlib, json, os; warnings.filterwarnings("ignore")
os.environ["NETWORKX_AUTOMATIC_BACKENDS"]=""
import networkx as nx, franken_networkx as fnx
try: nx.config.backend_priority=[]
except Exception: pass

def cases():
    out=[]
    for seed in range(8):
        out.append((f"gnp{seed}", nx.gnp_random_graph(80,0.05,seed=seed,directed=True), fnx.gnp_random_graph(80,0.05,seed=seed,directed=True)))
    # bidirectional heavy
    e=[(0,1),(1,0),(1,2),(2,1),(2,3),(0,3)]
    out.append(("bidir", nx.DiGraph(e), fnx.DiGraph(e)))
    # self loops
    e=[(0,0),(0,1),(1,0),(2,2),(1,2)]
    out.append(("selfloop", nx.DiGraph(e), fnx.DiGraph(e)))
    # isolated + no recip
    gn=nx.DiGraph([(0,1),(1,2),(2,3)]); gn.add_nodes_from([10,11]); gf=fnx.DiGraph([(0,1),(1,2),(2,3)]); gf.add_nodes_from([10,11])
    out.append(("isolated", gn, gf))
    # string labels
    out.append(("str", nx.DiGraph([("a","b"),("b","a"),("b","c")]), fnx.DiGraph([("a","b"),("b","a"),("b","c")])))
    out.append(("empty", nx.DiGraph(), fnx.DiGraph()))
    return out

fh=hashlib.sha256(); nh=hashlib.sha256(); mism=0; total=0
for name,gn,gf in cases():
    # overall
    on=nx.overall_reciprocity(gn) if gn.number_of_edges()>0 else 0.0
    of=fnx.overall_reciprocity(gf) if gf.number_of_edges()>0 else 0.0
    # per-node reciprocity (all nodes). nx yields None for total==0; fnx yields 0.0 -> normalize None->0.0 for compare
    if len(gn)>0:
        rn={k:(0.0 if v is None else v) for k,v in nx.reciprocity(gn, list(gn)).items()}
        rf={k:(0.0 if v is None else v) for k,v in dict(fnx.reciprocity(gf, list(gf))).items()}
    else:
        rn={}; rf={}
    total+=1
    ok = abs(on-of)<1e-12 and set(rn)==set(rf) and all(abs(rn[k]-rf[k])<1e-12 for k in rn)
    if not ok:
        mism+=1
        if mism<=3: print(f"MISMATCH {name}: overall nx={on} fnx={of}; sample diff", {k:(rn[k],rf.get(k)) for k in list(rn)[:3]})
    sig=json.dumps([round(of,12), sorted((str(k),round(v,12)) for k,v in rf.items())])
    sign=json.dumps([round(on,12), sorted((str(k),round(v,12)) for k,v in rn.items())])
    fh.update(sig.encode()); nh.update(sign.encode())
print(f"cases={total} mismatches={mism}")
print(f"fnx_sha={fh.hexdigest()}")
print(f"nx_sha ={nh.hexdigest()}")
print(f"MATCH={fh.hexdigest()==nh.hexdigest()}")
