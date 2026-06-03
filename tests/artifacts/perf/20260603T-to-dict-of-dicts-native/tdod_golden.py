import hashlib, json, networkx as nx, franken_networkx as fnx
def keyorder_sig(d):
    # full structure WITH inner key order (observable)
    return json.dumps([[repr(u), [repr(v) for v in d[u]]] for u in d])
def dataeq(dn, df):
    if set(dn)!=set(df): return False
    for u in dn:
        if list(map(repr,dn[u]))!=list(map(repr,df[u])): return False  # key order
        for v in dn[u]:
            if dict(dn[u][v])!=dict(df[u][v]): return False  # values
    return True
mism=0; sigs={}
for N,m,seed in [(1500,4,5),(300,3,11),(80,5,7),(40,2,1),(10,3,2)]:
    Gn=nx.barabasi_albert_graph(N,m,seed=seed); Gf=fnx.barabasi_albert_graph(N,m,seed=seed)
    # add some edge attrs to test data parity
    import random; r=random.Random(seed)
    for u,v in list(Gn.edges())[:N//2]:
        w=r.random(); Gn[u][v]['weight']=w; Gf[u][v]['weight']=w
    dn=nx.to_dict_of_dicts(Gn); df=fnx.to_dict_of_dicts(Gf)
    ok = dataeq(dn, df) and keyorder_sig(dn)==keyorder_sig(df)
    sigs[f"N{N}"]=hashlib.sha256(keyorder_sig(df).encode()).hexdigest()
    if not ok:
        mism+=1; print(f"MISMATCH N{N}")
print(f"mismatches={mism} cases={len(sigs)}")
# reference identity: d[u][v] must BE the live G[u][v] dict
G=fnx.barabasi_albert_graph(50,3,seed=9)
d=fnx.to_dict_of_dicts(G)
u,v=list(G.edges())[3]
assert d[u][v] is G[u][v], "not reference-identical!"
G[u][v]['z']=1; assert d[u][v]['z']==1, "mutation not reflected (not shared)!"
# self-loop
G.add_edge(7,7); d2=fnx.to_dict_of_dicts(G); assert 7 in d2[7], "self-loop missing"
# nodelist/edge_data still work (slow path)
d3=fnx.to_dict_of_dicts(G, nodelist=[0,1,2]); assert set(d3)=={0,1,2}
d4=fnx.to_dict_of_dicts(G, edge_data=5); 
assert all(d4[u2][v2]==5 for u2 in d4 for v2 in d4[u2]), "edge_data override broke"
print("reference identity + self-loop + nodelist + edge_data: OK")
print("TDOD_GOLDEN", hashlib.sha256("|".join(f"{k}={sigs[k]}" for k in sorted(sigs)).encode()).hexdigest())
