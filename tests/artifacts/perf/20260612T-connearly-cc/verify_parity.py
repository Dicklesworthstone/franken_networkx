import warnings, time
warnings.filterwarnings('ignore')
import networkx as nx, franken_networkx as fnx
mism=0; total=0
def check(G):
    global mism,total
    gf=fnx.Graph(G)
    try: rn=nx.is_connected(G)
    except Exception as e: rn=('E',type(e).__name__)
    try: rf=fnx.is_connected(gf)
    except Exception as e: rf=('E',type(e).__name__)
    total+=1
    if rn!=rf: mism+=1; print('MISMATCH', rn, rf, G.number_of_nodes())
# connected: complete, cycle, path, ba, ws
for n in [2,3,5,50,201]:
    check(nx.complete_graph(n)); check(nx.cycle_graph(n)); check(nx.path_graph(n))
check(nx.barabasi_albert_graph(500,4,seed=1)); check(nx.watts_strogatz_graph(500,6,0.3,seed=1))
# disconnected
check(nx.disjoint_union(nx.path_graph(5),nx.path_graph(5)))
check(nx.disjoint_union(nx.complete_graph(20),nx.complete_graph(30)))
check(nx.Graph([(0,1)]+[(5,6)]))  # two components + isolated-ish
# single node, empty (raises)
check(nx.Graph([(0,0)]))  # single node selfloop
g1=nx.Graph(); g1.add_node(0); check(g1)
# random
for seed in range(25):
    check(nx.gnp_random_graph(20+seed,0.12,seed=seed))
print('mismatches:',mism,'/',total)
def tm(f,r=11):
    ts=[]
    for _ in range(r): t0=time.perf_counter(); f(); ts.append(time.perf_counter()-t0)
    return min(ts)*1e3
for label,G in [('K201',nx.complete_graph(201)),('K601',nx.complete_graph(601)),('gnp_dense',nx.gnp_random_graph(800,0.3,seed=1)),('ba2000',nx.barabasi_albert_graph(2000,4,seed=1)),('ws2000_disc',nx.disjoint_union(nx.path_graph(1000),nx.path_graph(1000)))]:
    gf=fnx.Graph(G)
    print('%-14s nx=%.4f fnx=%.4f ratio=%.2f'%(label, tm(lambda:nx.is_connected(G)), tm(lambda:fnx.is_connected(gf)), tm(lambda:fnx.is_connected(gf))/tm(lambda:nx.is_connected(G))))
