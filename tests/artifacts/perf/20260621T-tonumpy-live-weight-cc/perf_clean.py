import time, numpy as np, networkx as nx, franken_networkx as fnx
from franken_networkx import _fnx
def warm(fn,n=15):
    ts=[]
    for _ in range(n):
        t=time.perf_counter(); fn(); ts.append(time.perf_counter()-t)
    return min(ts)*1e3
def build(directed,N,degree=4):
    g0=fnx.gnm_random_graph(N,N*degree,seed=7,directed=directed)
    edges=list(g0.edges()); nodes=list(g0)
    Cls=fnx.DiGraph if directed else fnx.Graph
    G=Cls(); G.add_nodes_from(nodes); G.add_edges_from(edges)
    for u,v in edges: G[u][v]['weight']=(u*7+v)%13+1   # mutate -> dirty
    Gn=(nx.DiGraph if directed else nx.Graph)(); Gn.add_nodes_from(nodes)
    for u,v in edges: Gn.add_edge(u,v,weight=(u*7+v)%13+1)
    return G,Gn
def old_path(G):
    nl=list(G); G._fnx_sync_edge_attrs_to_inner()
    rows,cols,data=_fnx.adjacency_arrays(G,nl,'weight',1.0)
    m=np.full((len(nl),len(nl)),0.0)
    if rows: m[np.asarray(rows),np.asarray(cols)]=np.asarray(data,dtype=m.dtype)
    return m
print(f"{'case':22s} {'OLD(sync)':>10s} {'NEW(live)':>10s} {'nx':>8s} {'new/old':>8s} {'new/nx':>8s}")
for N in (700,1500,3000):
    for directed in (False,True):
        G,Gn=build(directed,N)
        assert _fnx.dijkstra_weight_cache_token(G)[2]  # dirty
        # parity sanity
        assert np.array_equal(fnx.to_numpy_array(G), nx.to_numpy_array(Gn))
        for _ in range(3): fnx.to_numpy_array(G); old_path(G); nx.to_numpy_array(Gn)
        tnew=warm(lambda:fnx.to_numpy_array(G))
        told=warm(lambda:old_path(G))
        tnx=warm(lambda:nx.to_numpy_array(Gn))
        lbl=f"N={N} {'DiGraph' if directed else 'Graph'}"
        print(f"{lbl:22s} {told:9.3f}m {tnew:9.3f}m {tnx:7.3f}m {told/tnew:7.2f}x {tnx/tnew:7.2f}x")
