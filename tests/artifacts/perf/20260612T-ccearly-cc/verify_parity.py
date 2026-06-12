import warnings, time, hashlib, json
warnings.filterwarnings('ignore')
import networkx as nx, franken_networkx as fnx
def canon_cc(comps): return sorted(tuple(sorted(c)) for c in comps)
mism=0; total=0
graphs=[]
for n in [2,3,5,50,201]: graphs.append(('K%d'%n,nx.complete_graph(n)))
graphs.append(('cycle50',nx.cycle_graph(50))); graphs.append(('path50',nx.path_graph(50)))
graphs.append(('ba500',nx.barabasi_albert_graph(500,4,seed=1)))
graphs.append(('2comp',nx.disjoint_union(nx.complete_graph(20),nx.complete_graph(30))))
graphs.append(('3comp',nx.disjoint_union(nx.disjoint_union(nx.path_graph(10),nx.cycle_graph(8)),nx.complete_graph(15))))
graphs.append(('isolates',nx.Graph([(0,1),(5,6)]+[(10,10)])))
for seed in range(20): graphs.append(('gnp%d'%seed, nx.gnp_random_graph(25+seed,0.08,seed=seed)))
fps=[]
for name,G in graphs:
    gf=fnx.Graph(G)
    # connected_components (set comparison)
    a=canon_cc(nx.connected_components(G)); b=canon_cc(fnx.connected_components(gf))
    # number
    nn=nx.number_connected_components(G); nf=fnx.number_connected_components(gf)
    # node_connected_component for node 0 (if present)
    nc_ok=True
    if len(G)>0:
        node=list(G)[0]
        nc_ok = (nx.node_connected_component(G,node)==fnx.node_connected_component(gf,node))
    total+=1
    if a!=b or nn!=nf or not nc_ok:
        mism+=1; print('MISMATCH',name,'cc',a==b,'num',nn==nf,'nc',nc_ok)
    fps.append((name,b,nn))
sha=hashlib.sha256(json.dumps(fps,sort_keys=True,default=str).encode()).hexdigest()
print('mismatches:',mism,'/',total); print('GOLDEN',sha)
def tm(f,r=11):
    ts=[]
    for _ in range(r): t0=time.perf_counter(); f(); ts.append(time.perf_counter()-t0)
    return min(ts)*1e3
for label,G in [('K601',nx.complete_graph(601)),('gnp_dense',nx.gnp_random_graph(800,0.3,seed=1)),('ba2000',nx.barabasi_albert_graph(2000,4,seed=1)),('3comp_dense',nx.disjoint_union(nx.complete_graph(300),nx.complete_graph(300)))]:
    gf=fnx.Graph(G)
    print('%-14s numcc: nx=%.4f fnx=%.4f ratio=%.2f | node_cc: nx=%.4f fnx=%.4f ratio=%.2f'%(label, tm(lambda:nx.number_connected_components(G)), tm(lambda:fnx.number_connected_components(gf)), tm(lambda:fnx.number_connected_components(gf))/tm(lambda:nx.number_connected_components(G)), tm(lambda:nx.node_connected_component(G,0)), tm(lambda:fnx.node_connected_component(gf,0)), tm(lambda:fnx.node_connected_component(gf,0))/tm(lambda:nx.node_connected_component(G,0))))
