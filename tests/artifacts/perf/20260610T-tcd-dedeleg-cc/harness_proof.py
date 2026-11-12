import warnings, hashlib, json; warnings.filterwarnings("ignore")
import networkx as nx, franken_networkx as fnx

def fp(TC):
    # ordered fingerprint: nodes in order, edges in adj-iteration order with attrs
    parts=["N:"+ "|".join(f"{n!r}:{sorted(d.items())!r}" for n,d in TC.nodes(data=True))]
    parts.append("E:"+ "|".join(f"{u!r}->{v!r}:{sorted(d.items())!r}" for u,v,d in TC.edges(data=True)))
    parts.append("G:"+repr(sorted(TC.graph.items())))
    return "\n".join(parts)

def cases():
    out=[]
    for seed in range(8):
        out.append((f"gn{seed}", nx.gn_graph(200,seed=seed), fnx.gn_graph(200,seed=seed), None))
    for seed in range(4):
        dn=nx.gnp_random_graph(150,0.03,seed=seed,directed=True)
        # make a DAG: keep only u<v edges
        dn2=nx.DiGraph((u,v) for u,v in dn.edges() if u<v)
        dn2.add_nodes_from(dn.nodes())
        df2=fnx.DiGraph((u,v) for u,v in dn.edges() if u<v); df2.add_nodes_from(dn.nodes())
        out.append((f"dag{seed}", dn2, df2, None))
    # chain
    out.append(("chain", nx.DiGraph([(i,i+1) for i in range(30)]), fnx.DiGraph([(i,i+1) for i in range(30)]), None))
    # diamond / multiple paths
    e=[(0,1),(0,2),(1,3),(2,3),(3,4),(1,4)]
    out.append(("diamond", nx.DiGraph(e), fnx.DiGraph(e), None))
    # with edge attrs
    gn=nx.DiGraph(); gf=fnx.DiGraph()
    for i,(u,v) in enumerate([(0,1),(1,2),(2,3),(0,2)]):
        gn.add_edge(u,v,w=i); gf.add_edge(u,v,w=i)
    gn.graph["lbl"]="x"; gf.graph["lbl"]="x"
    out.append(("attrs", gn, gf, None))
    # explicit topo_order
    e=[(5,3),(3,1),(5,1),(4,3)]
    tn=list(nx.topological_sort(nx.DiGraph(e)))
    out.append(("topo_param", nx.DiGraph(e), fnx.DiGraph(e), tn))
    # empty + single
    out.append(("empty", nx.DiGraph(), fnx.DiGraph(), None))
    sn=nx.DiGraph(); sn.add_node(7); sf=fnx.DiGraph(); sf.add_node(7)
    out.append(("single", sn, sf, None))
    # string labels
    es=[("a","b"),("b","c"),("a","c"),("c","d")]
    out.append(("str", nx.DiGraph(es), fnx.DiGraph(es), None))
    return out

fh=hashlib.sha256(); nh=hashlib.sha256(); mism=0; total=0
for name,gn,gf,topo in cases():
    rn=nx.transitive_closure_dag(gn, topo) if topo else nx.transitive_closure_dag(gn)
    rf=fnx.transitive_closure_dag(gf, topo) if topo else fnx.transitive_closure_dag(gf)
    total+=1
    a=fp(rn); b=fp(rf)
    if a!=b:
        mism+=1
        if mism<=3:
            for ln_n,ln_f in zip(a.split("\n"),b.split("\n")):
                if ln_n!=ln_f: print(f"MISMATCH {name}:\n  nx ={ln_n[:120]}\n  fnx={ln_f[:120]}"); break
    nh.update(a.encode()); nh.update(b"||"); fh.update(b.encode()); fh.update(b"||")
print(f"cases={total} mismatches={mism}")
print(f"fnx_sha={fh.hexdigest()}")
print(f"nx_sha ={nh.hexdigest()}")
print(f"MATCH={fh.hexdigest()==nh.hexdigest()}")
