import time, franken_networkx as fnx
N=900
rows=[(i%N,(i*7+3)%N,k,{'w':i%5}) for i,k in enumerate(range(N*4))]
# but keys must be valid; use auto. Build realistic 4-tuples from a real subgraph copy
g=fnx.MultiGraph(); g.add_edges_from([(i%N,(i*7+3)%N) for i in range(N*4)])
four=[(u,v,k,dict(d)) for u,v,k,d in g.edges(keys=True,data=True)]
def wm(fn,n=9):
    ts=[]
    for _ in range(n):
        t=time.perf_counter(); fn(); ts.append(time.perf_counter()-t)
    return min(ts)*1e3
def build_list():
    r=fnx.MultiGraph(); r.add_nodes_from(range(N)); r.add_edges_from(four); return r
def build_gen():
    r=fnx.MultiGraph(); r.add_nodes_from(range(N)); r.add_edges_from((u,v,k,dict(d)) for u,v,k,d in four); return r
for _ in range(3): build_list(); build_gen()
print("add_edges_from LIST of 4-tuples : %.3f ms"%wm(build_list))
print("add_edges_from GEN  of 4-tuples : %.3f ms"%wm(build_gen))
# verify identical result
a=build_list(); b=build_gen()
print("same #edges:", a.number_of_edges()==b.number_of_edges()==len(four))
# does batch accept 4-tuples? check _try_add_attr_edges_from_batch on fresh
r=fnx.MultiGraph()
batch=getattr(r,'_try_add_attr_edges_from_batch',None)
print("batch returns (4-tuple list):", batch(four) if batch else "no batch attr")
print("  -> edges after batch:", r.number_of_edges())
