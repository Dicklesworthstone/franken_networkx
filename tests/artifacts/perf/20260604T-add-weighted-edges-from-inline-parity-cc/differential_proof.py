import networkx as nx, franken_networkx as fnx, hashlib, json

def trial(GraphCls, edges, weight, attr):
    G = GraphCls()
    try:
        G.add_weighted_edges_from(edges, weight=weight, **attr)
        err=None
    except BaseException as e:
        err=f"{type(e).__name__}: {e}"
    nodes = sorted(map(str,G.nodes()))
    edata = sorted((str(u),str(v),json.dumps(d,sort_keys=True,default=str)) for u,v,d in G.edges(data=True))
    return (nodes, edata, err)

cases = [
    ("bad_arity_short", [(1,2,5),(3,4,6),(5,)], "weight", {}),
    ("bad_arity_long",  [(1,2,5),(8,9,3,4)], "weight", {}),
    ("v_none_mid",      [(1,2,5),(7,None,9)], "weight", {}),
    ("u_none_mid",      [(1,2,5),(None,7,9)], "weight", {}),
    ("v_unhashable",    [(1,2,5),(7,[3],9)], "weight", {}),
    ("u_unhashable",    [(1,2,5),([3],7,9)], "weight", {}),
    ("all_valid",       [(1,2,5),(2,3,6),(3,4,7)], "weight", {}),
    ("with_attr",       [(1,2,5),(3,4,6)], "weight", {"color":"r"}),
    ("custom_weightkey",[(1,2,5),(3,4,6)], "cost", {}),
    ("v_none_first",    [(1,None,9),(2,3,4)], "weight", {}),
    ("empty",           [], "weight", {}),
    ("self_loop",       [(1,1,2),(2,2,3),(3,)], "weight", {}),
    ("dup",             [(1,2,5),(1,2,7),(9,)], "weight", {}),
]
mismatch=0; golden=[]
for gn, GN, GF in [("Graph",nx.Graph,fnx.Graph),("DiGraph",nx.DiGraph,fnx.DiGraph),
                   ("MultiGraph",nx.MultiGraph,fnx.MultiGraph),("MultiDiGraph",nx.MultiDiGraph,fnx.MultiDiGraph)]:
    for name,edges,w,attr in cases:
        rn=trial(GN,edges,w,attr); rf=trial(GF,edges,w,attr)
        ok=(rn==rf)
        if not ok:
            mismatch+=1; print(f"MISMATCH [{gn}] {name}\n  nx :{rn}\n  fnx:{rf}")
        golden.append(json.dumps({"g":gn,"c":name,"r":rn},sort_keys=True,default=str))
print(f"\nTOTAL={len(cases)*4} mismatch={mismatch}")
print("GOLDEN_SHA256", hashlib.sha256("\n".join(golden).encode()).hexdigest())
