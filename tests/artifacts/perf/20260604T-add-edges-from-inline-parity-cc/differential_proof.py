import networkx as nx
import franken_networkx as fnx
import hashlib, json

def trial(mod, GraphCls, edges, attr):
    G = GraphCls()
    try:
        if callable(edges):
            G.add_edges_from(edges(), **attr)
        else:
            G.add_edges_from(edges, **attr)
        err = None
    except BaseException as e:
        err = f"{type(e).__name__}: {e}"
    nodes = sorted(G.nodes(), key=lambda x:(str(type(x)),str(x)))
    try:
        edgelist = sorted(tuple(sorted((str(u),str(v)))) for u,v in G.edges())
    except Exception:
        edgelist = "?"
    # also capture edge data for attr cases
    edata = sorted((str(u),str(v),json.dumps(d,sort_keys=True,default=str)) for u,v,d in G.edges(data=True))
    return (list(map(str,nodes)), edgelist, edata, err)

def gen_partial():
    yield (1,2); yield (3,4); yield (5,)   # malformed mid-stream

def gen_raises():
    yield (1,2); yield (3,4); raise RuntimeError("boom")

def gen_raises_then_would_bad():
    yield (10,11)
    raise ValueError("midstream")

cases = [
    ("partial_then_bad", [(1,2),(3,4),(5,)], {}),
    ("first_bad", [(5,),(1,2)], {}),
    ("u_none", [(None,2),(3,4)], {}),
    ("v_none", [(1,None),(3,4)], {}),
    ("none_none", [(None,None)], {}),
    ("v_none_after_valid", [(7,8),(1,None)], {}),
    ("bad_3tuple", [(1,2),(3,4,5,6)], {}),
    ("list_edges_ok", [[1,2],[3,4]], {}),
    ("list_then_bad", [[1,2],[3,4],[5]], {}),
    ("string_edge_ok", ["ab","cd"], {}),  # 2-char strings are edges
    ("string_bad", [(1,2),"oops"], {}),
    ("nonlen_none_item", [(1,2),None], {}),
    ("nonlen_int_item", [(1,2),5], {}),
    ("unhashable_v", [(1,[9]),(2,3)], {}),
    ("unhashable_u", [([9],1),(2,3)], {}),
    ("unhashable_after_valid", [(4,5),(6,[9])], {}),
    ("with_attr_prefix", [(1,2),(3,4),(5,)], {"weight":7}),
    ("3tuple_data_ok", [(1,2,{"w":1}),(3,4,{"w":2})], {}),
    ("dup_then_bad", [(1,2),(1,2),(9,)], {}),
    ("gen_partial_bad", gen_partial, {}),
    ("gen_raises", gen_raises, {}),
    ("gen_raises2", gen_raises_then_would_bad, {}),
    ("empty", [], {}),
    ("all_valid", [(1,2),(2,3),(3,4),(4,1)], {"color":"r"}),
    ("self_loop_then_bad", [(1,1),(2,2),(3,)], {}),
]

mismatch = 0
golden = []
for GraphName, GraphN, GraphF in [("Graph", nx.Graph, fnx.Graph), ("DiGraph", nx.DiGraph, fnx.DiGraph)]:
    for name, edges, attr in cases:
        rn = trial(GraphN, GraphN, edges, attr)
        rf = trial(GraphF, GraphF, edges, attr)
        ok = (rn == rf)
        if not ok:
            mismatch += 1
            print(f"MISMATCH [{GraphName}] {name}")
            print("  nx :", rn)
            print("  fnx:", rf)
        golden.append(json.dumps({"g":GraphName,"case":name,"r":rn}, sort_keys=True, default=str))

print(f"\nTOTAL cases={len(cases)*2} mismatch={mismatch}")
print("GOLDEN_SHA256", hashlib.sha256("\n".join(golden).encode()).hexdigest())
