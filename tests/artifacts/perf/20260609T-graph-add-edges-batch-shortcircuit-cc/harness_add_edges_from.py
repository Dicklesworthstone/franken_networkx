import time, sys, hashlib, json
import networkx as nx
import franken_networkx as fnx

def edges_repr(g):
    out=[]
    for u,v,d in g.edges(data=True):
        out.append((repr(u),repr(v),sorted((str(k),repr(val)) for k,val in d.items())))
    out.sort()
    return (sorted(map(repr,g.nodes())), out)

SCN = {
  "plain_int":   lambda g: g.add_edges_from([(i,(i*7+3)%500) for i in range(400)]),
  "plain_str":   lambda g: g.add_edges_from([(str(i),str((i*7+3)%500)) for i in range(400)]),
  "weighted":    lambda g: g.add_edges_from([(i,(i*7+3)%500,{"weight":i%5,"c":"x"}) for i in range(400)]),
  "mixed_2_3":   lambda g: g.add_edges_from([(0,1),(1,2,{"w":9}),(2,3),(3,4,{"w":1})]),
  "tuple_nodes": lambda g: g.add_edges_from([((0,0),(0,1)),((0,1),(0,2),{"w":1})]),
  "global_attr": lambda g: g.add_edges_from([(0,1),(1,2),(2,3)], color="red"),
  "with_dups":   lambda g: g.add_edges_from([(1,2),(2,1),(1,2,{"w":5})]),
  "list_edges":  lambda g: g.add_edges_from([[0,1],[1,2],[2,3]]),
  "3rd_nondict": lambda g: g.add_edges_from([(0,1,7)]) if g.is_multigraph() else None,
  "bad_arity":   lambda g: _expect_err(g, [(0,1),(1,)]),
  "none_node":   lambda g: _expect_err(g, [(0,1),(2,None)]),
  "preexist":    lambda g: (g.add_edges_from([(0,1),(1,2)]), g.add_edges_from([(2,3,{"w":1}),(0,1)]))[-1],
  "gen_weighted":lambda g: g.add_edges_from((i,(i+1)%50,{"w":i}) for i in range(50)),
  "big_weighted":lambda g: g.add_edges_from([(i,(i*13+1)%2000,{"weight":float(i%7)}) for i in range(2000)]),
}
def _expect_err(g, edges):
    try:
        g.add_edges_from(edges); return "NOERR"
    except Exception as e:
        return f"{type(e).__name__}"

def run(mod):
    out={}
    for name,build in SCN.items():
        g=mod.Graph()
        try:
            r=build(g)
            if isinstance(r,str): out[name]=("ERRMODE",r,edges_repr(g))
            elif r is None and name=="3rd_nondict": out[name]="SKIP"
            else: out[name]=edges_repr(g)
        except Exception as e:
            out[name]=f"EXC:{type(e).__name__}:{e}"
    return out

if __name__=="__main__":
    f=run(fnx); n=run(nx)
    mism=[k for k in SCN if f[k]!=n[k]]
    print("MISMATCHES:",mism)
    for k in mism: print(f"  {k}:\n    fnx={f[k]}\n    nx ={n[k]}")
    sha=hashlib.sha256(json.dumps(f,sort_keys=True,default=str).encode()).hexdigest()
    print("fnx sha:",sha)
    print("PARITY_OK" if not mism else "PARITY_FAIL")
    def measure(fn,runs=7,warm=2):
        for _ in range(warm): fn()
        ts=[]
        for _ in range(runs):
            s=time.perf_counter(); fn(); ts.append((time.perf_counter()-s)*1000)
        ts.sort(); return ts[len(ts)//2]
    ei=[(i,(i*7+3)%20000) for i in range(20000)]
    ew=[(i,(i*7+3)%20000,{"weight":i%5}) for i in range(20000)]
    for label,ed in [("int2tuple",ei),("weighted3tuple",ew)]:
        tf=measure(lambda:(lambda g:g.add_edges_from(ed))(fnx.Graph())); tn=measure(lambda:(lambda g:g.add_edges_from(ed))(nx.Graph()))
        print(f"BENCH add_edges_from 20k {label}: fnx {tf:.2f}ms nx {tn:.2f}ms ratio {tf/tn:.2f}")
