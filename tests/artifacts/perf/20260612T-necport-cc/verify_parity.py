import warnings, time, random
warnings.filterwarnings('ignore')
import networkx as nx, franken_networkx as fnx
mism=0; n_true=0; n_false=0
for seed in range(40):
    G=nx.gnp_random_graph(15+seed,0.12,seed=seed,directed=True)
    rng=random.Random(seed)
    # mix: some with negative cycles, some without
    lo=-5 if seed%2==0 else 1
    for u,v in G.edges(): G.edges[u,v]['weight']=rng.randint(lo,9)
    gf=fnx.DiGraph(G)
    r_nx=nx.negative_edge_cycle(G,weight='weight'); r_fx=fnx.negative_edge_cycle(gf,weight='weight')
    if r_nx!=r_fx: mism+=1; print('MISMATCH seed',seed,'nx',r_nx,'fnx',r_fx)
    n_true+= r_nx is True; n_false+= r_nx is False
# edge cases: empty edges, self neg loop, heuristic=False
e=nx.DiGraph(); e.add_nodes_from([0,1]); 
print('empty-edges match:', nx.negative_edge_cycle(e,weight='weight')==fnx.negative_edge_cycle(fnx.DiGraph(e),weight='weight'))
sl=nx.DiGraph([(0,1),(1,1)]); sl[1][1]['weight']=-3; 
print('neg-selfloop match:', nx.negative_edge_cycle(sl,weight='weight')==fnx.negative_edge_cycle(fnx.DiGraph(sl),weight='weight'))
G=nx.gnp_random_graph(30,0.1,seed=3,directed=True)
for u,v in G.edges(): G.edges[u,v]['weight']=random.Random(3).randint(-3,9)
print('heuristic=False match:', nx.negative_edge_cycle(G,weight='weight',heuristic=False)==fnx.negative_edge_cycle(fnx.DiGraph(G),weight='weight',heuristic=False))
print('mismatches:',mism,'/40  (true:%d false:%d)'%(n_true,n_false))
def tm(f,r=7):
    ts=[]
    for _ in range(r): t0=time.perf_counter(); f(); ts.append(time.perf_counter()-t0)
    return min(ts)*1e3
rng=random.Random(1)
for nn in [200,300,500]:
    G=nx.gnp_random_graph(nn,0.04,seed=1,directed=True)
    for u,v in G.edges(): G.edges[u,v]['weight']=rng.randint(1,9)
    gf=fnx.DiGraph(G)
    print('bench n=%d: nx=%.3f fnx=%.3f ratio=%.2f'%(nn, tm(lambda:nx.negative_edge_cycle(G,weight='weight')), tm(lambda:fnx.negative_edge_cycle(gf,weight='weight')), tm(lambda:fnx.negative_edge_cycle(gf,weight='weight'))/tm(lambda:nx.negative_edge_cycle(G,weight='weight'))))
