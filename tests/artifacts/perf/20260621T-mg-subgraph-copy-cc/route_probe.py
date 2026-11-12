import time, networkx as nx, franken_networkx as fnx
N=900
edges=[(i%N,(i*7+3)%N) for i in range(N*4)]
def mk(cls):
    g=cls(); g.add_edges_from(edges)
    for i,(u,v) in enumerate(edges):
        pass
    return g
gf=mk(fnx.MultiGraph); gn=mk(nx.MultiGraph)
# add some node + edge attrs + graph attr for correctness coverage
gf.graph['name']='t'; gn.graph['name']='t'
for n in list(gf)[:50]: gf.nodes[n]['c']=n; gn.nodes[n]['c']=n
sub=list(range(400))
drop=[x for x in gf if x not in set(sub)]

def route_copy(g, keep):
    keep_set=set(keep)
    r=g._native_copy()
    r.remove_nodes_from([x for x in g if x not in keep_set])
    return r

def wm(fn,n=11):
    ts=[]
    for _ in range(n):
        t=time.perf_counter(); fn(); ts.append(time.perf_counter()-t)
    return min(ts)*1e3

a=gf.subgraph(sub).copy()
b=route_copy(gf, sub)
c=gn.subgraph(sub).copy()
def sig(G):
    import collections
    nodes=sorted(G.nodes(data=True), key=lambda t:t[0])
    nattr=[(n,tuple(sorted(d.items()))) for n,d in nodes]
    edges=sorted((min(u,v),max(u,v),k,tuple(sorted(d.items()))) for u,v,k,d in G.edges(keys=True,data=True))
    return (G.number_of_nodes(),G.number_of_edges(),tuple(nattr),tuple(edges),tuple(sorted(G.graph.items())))
print("route==official fnx:", sig(a)==sig(b))
print("route==nx:", sig(b)==sig(c))
print("official==nx:", sig(a)==sig(c))
for _ in range(3): gf.subgraph(sub).copy(); route_copy(gf,sub); gn.subgraph(sub).copy()
print("official fnx subgraph.copy : %.3f ms"%wm(lambda:gf.subgraph(sub).copy()))
print("ROUTE  copy+remove         : %.3f ms"%wm(lambda:route_copy(gf,sub)))
print("nx subgraph.copy           : %.3f ms"%wm(lambda:gn.subgraph(sub).copy()))
