import time, numpy as np, networkx as nx, franken_networkx as fnx
from franken_networkx import _fnx

def warm(fn,n=13):
    ts=[]
    for _ in range(n):
        t=time.perf_counter(); fn(); ts.append(time.perf_counter()-t)
    return min(ts)*1e3

def wval(u,v,wk):
    if wk=='int': return (u*7+v)%13+1
    if wk=='float': return ((u*7+v)%13+1)*0.5
    if wk=='bool': return bool((u+v)%2)
    if wk=='str': return str(((u*7+v)%13+1))
    if wk=='strbad': return 'abc' if (u+v)%5==0 else (u%3+1)
    if wk=='nan': return float('nan') if (u+v)%7==0 else 1.0
    if wk=='inf': return float('inf') if (u+v)%7==0 else 2.0

def make(directed, wk, mode, N=700):
    g0=fnx.gnm_random_graph(N, N*4, seed=7, directed=directed)
    edges=list(g0.edges()); nodes=list(g0)
    Cls=fnx.DiGraph if directed else fnx.Graph
    half=(wk=='missing')
    G=Cls(); G.add_nodes_from(nodes)
    if mode=='con':
        if half:
            ec=[(u,v,{'weight':(u%3+1)}) if i%2==0 else (u,v) for i,(u,v) in enumerate(edges)]
        else:
            ec=[(u,v,{'weight':wval(u,v,wk)}) for (u,v) in edges]
        G.add_edges_from(ec)
    else:
        G.add_edges_from(edges)
        for i,(u,v) in enumerate(edges):
            if half:
                if i%2==0: G[u][v]['weight']=(u%3+1)
            else:
                G[u][v]['weight']=wval(u,v,wk)
    return G, nodes, edges

def nx_twin(directed, nodes, edges, wk):
    Gn=(nx.DiGraph if directed else nx.Graph)()
    Gn.add_nodes_from(nodes)
    half=(wk=='missing')
    for i,(u,v) in enumerate(edges):
        if half:
            Gn.add_edge(u,v)
            if i%2==0: Gn[u][v]['weight']=(u%3+1)
        else:
            Gn.add_edge(u,v, weight=wval(u,v,wk))
    return Gn

# 1) byte-identity: live(dirty) vs inner(not-dirty), ALL kinds
print("=== byte-identity: live(dirty) == inner(not-dirty), all kinds ===")
bi=bif=0
for directed in (False,True):
    for wk in ('int','float','bool','str','strbad','nan','inf','missing'):
        Gm,_,_=make(directed,wk,'mut'); Gc,_,_=make(directed,wk,'con')
        assert _fnx.dijkstra_weight_cache_token(Gm)[2] and not _fnx.dijkstra_weight_cache_token(Gc)[2]
        for nonedge in (0.0,-1.0):
            for dt in (None,np.float32):
                a=fnx.to_numpy_array(Gm,nonedge=nonedge,dtype=dt)
                b=fnx.to_numpy_array(Gc,nonedge=nonedge,dtype=dt)
                bi+=1
                if not np.array_equal(a,b,equal_nan=True):
                    bif+=1; print(f"  DIVERGE d={directed} wk={wk} ne={nonedge} dt={dt}")
print(f"  {bi-bif}/{bi} live==inner byte-identical")

# 2) fnx-vs-nx (numeric kinds; nx errors on strings by design)
print("=== fnx(dirty live) == nx, numeric kinds ===")
nc=ncf=0
for directed in (False,True):
    for wk in ('int','float','bool','nan','inf','missing'):
        Gm,nodes,edges=make(directed,wk,'mut')
        Gn=nx_twin(directed,nodes,edges,wk)
        for nonedge in (0.0,-1.0):
            for dt in (None,np.float32):
                a=fnx.to_numpy_array(Gm,nonedge=nonedge,dtype=dt)
                b=nx.to_numpy_array(Gn,nonedge=nonedge,dtype=dt)
                nc+=1
                if not np.array_equal(a,b,equal_nan=True):
                    ncf+=1; print(f"  MISMATCH d={directed} wk={wk} ne={nonedge} dt={dt}")
print(f"  {nc-ncf}/{nc} fnx==nx byte-identical")

# 3) PERF: old(sync+inner) vs new(live) vs nx, dirty graphs
print("\n=== PERF dirty path: OLD(sync) vs NEW(live) vs nx ===")
def old_path(G,nodelist):
    G._fnx_sync_edge_attrs_to_inner()
    rows,cols,data=_fnx.adjacency_arrays(G,nodelist,'weight',1.0)
    m=np.full((len(nodelist),len(nodelist)),0.0)
    if rows: m[np.asarray(rows),np.asarray(cols)]=np.asarray(data,dtype=m.dtype)
    return m
for N in (700,1500):
    for directed in (False,True):
        Gm,nodes,edges=make(directed,'int','mut',N=N)
        Gn=nx_twin(directed,nodes,edges,'int')
        nl=list(Gm)
        # NOTE: old_path mutates dirty->clean via sync; rebuild fresh each timing
        def fresh_old():
            G,_,_=make(directed,'int','mut',N=N); return old_path(G,list(G))
        for _ in range(3): fnx.to_numpy_array(Gm); nx.to_numpy_array(Gn); fresh_old()
        tnew=warm(lambda:fnx.to_numpy_array(make(directed,'int','mut',N=N)[0]))
        told=warm(fresh_old)
        tnx=warm(lambda:nx.to_numpy_array(Gn))
        lbl=('DiGraph' if directed else 'Graph')
        print(f"  N={N} {lbl:8s} OLD(sync)={told:.3f}ms NEW(live)={tnew:.3f}ms nx={tnx:.3f}ms | new-vs-old={told/tnew:.2f}x new-vs-nx={tnx/tnew:.2f}x")
