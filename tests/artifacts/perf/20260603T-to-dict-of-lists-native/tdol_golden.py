import hashlib, json, networkx as nx, franken_networkx as fnx
def sig(d):
    return json.dumps([[repr(u), [repr(v) for v in d[u]]] for u in d])  # node order + list order
mism=0; sigs={}
for N,m,seed in [(1500,4,5),(300,3,11),(80,5,7),(40,2,1),(10,3,2)]:
    Gn=nx.barabasi_albert_graph(N,m,seed=seed); Gf=fnx.barabasi_albert_graph(N,m,seed=seed)
    dn=nx.to_dict_of_lists(Gn); df=fnx.to_dict_of_lists(Gf)
    s=sig(dn)
    sigs[f"N{N}"]=hashlib.sha256(sig(df).encode()).hexdigest()
    if s!=sig(df):
        mism+=1; print(f"MISMATCH N{N}")
        for u in dn:
            if list(map(repr,dn[u]))!=list(map(repr,df[u])): print(' node',u,'nx',dn[u][:6],'fnx',df[u][:6]); break
print(f"mismatches={mism} cases={len(sigs)}")
# self-loop + nodelist fallback
G=fnx.barabasi_albert_graph(40,3,seed=9); G.add_edge(5,5)
Gn=nx.barabasi_albert_graph(40,3,seed=9); Gn.add_edge(5,5)
assert fnx.to_dict_of_lists(G)[5]==nx.to_dict_of_lists(Gn)[5], "self-loop list mismatch"
d3=fnx.to_dict_of_lists(G, nodelist=[0,1,2]); dn3=nx.to_dict_of_lists(Gn, nodelist=[0,1,2])
assert {k:list(map(repr,v)) for k,v in d3.items()}=={k:list(map(repr,v)) for k,v in dn3.items()}, "nodelist mismatch"
# value type: nx returns list
assert isinstance(fnx.to_dict_of_lists(G)[0], list)
print("self-loop + nodelist + type: OK")
print("TDOL_GOLDEN", hashlib.sha256("|".join(f"{k}={sigs[k]}" for k in sorted(sigs)).encode()).hexdigest())
