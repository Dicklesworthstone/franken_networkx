import franken_networkx as fnx, networkx as nx, random, json, hashlib

def build(M, seed, n=40, e=120, sl=True):
    r=random.Random(seed); g=M()
    for x in [5,2,9,1,7,30,3,0]: g.add_node(x, lbl=f"n{x}")
    g.add_nodes_from(range(n))
    g.graph['gattr']={'nested':[1,2]}; g.graph['v']=7
    for _ in range(e):
        u,v=r.randint(0,n-1),r.randint(0,n-1)
        if not sl and u==v: v=(v+1)%n
        k=r.randint(0,3)
        if k==0: g.add_edge(u,v,w=r.random())
        elif k==1: g.add_edge(u,v,w=r.randint(1,9),tag='a')
        elif k==2: g.add_edge(u,v)
        else: g.add_edge(u,v,data=[u,v])
    return g

def snap(g):
    return {"nodes": list(g.nodes(data=True)), "edges": list(g.edges(keys=True, data=True)),
            "graph": dict(g.graph), "type": type(g).__name__,
            "n": g.number_of_nodes(), "m": g.number_of_edges()}

records=[]; mism=0
for label, Mf, Mn in [("MultiGraph", fnx.MultiGraph, nx.MultiGraph), ("MultiDiGraph", fnx.MultiDiGraph, nx.MultiDiGraph)]:
    for seed in (1,2,3):
        for sl in (True, False):
            gf=build(Mf,seed,sl=sl); gn=build(Mn,seed,sl=sl)
            cf=gf.copy(); cn=gn.copy()
            sf=snap(cf); sn=snap(cn)
            if sf != sn:
                mism+=1
                for k in sf:
                    if sf[k]!=sn[k]: print(f"  COPY MISMATCH {label} s={seed} sl={sl} key={k}"); break
            # shallow-value semantics + independent dict
            shared=False
            for u,v,k,d in cf.edges(keys=True, data=True):
                if 'data' in d:
                    assert cf[u][v][k]['data'] is gf[u][v][k]['data']
                    assert cf[u][v][k] is not gf[u][v][k]
                    shared=True; break
            assert shared, "expected a shared-container edge"
            assert cf.graph['gattr'] is gf.graph['gattr'], "graph attr value shared"
            # mutating the copy's structure must not touch the original
            cf.add_edge(999, 998)
            assert not gf.has_edge(999, 998), "copy structurally independent"
            assert type(cf) is type(gf)
            records.append([label,seed,sl,[sf["nodes"], sf["edges"], sf["graph"]]])
blob=json.dumps(records, sort_keys=True, default=str).encode()
print(f"mismatches={mism}")
print(f"COPY_GOLDEN {hashlib.sha256(blob).hexdigest()}")
