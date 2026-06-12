import warnings, time, random
warnings.filterwarnings('ignore')
import networkx as nx, franken_networkx as fnx
mism=0; total=0
def check(G):
    global mism, total
    gf=fnx.DiGraph(G) if G.is_directed() else fnx.Graph(G)
    try: rn=nx.is_eulerian(G)
    except Exception as e: rn=('E',type(e).__name__)
    try: rf=fnx.is_eulerian(gf)
    except Exception as e: rf=('E',type(e).__name__)
    total+=1
    if rn!=rf: mism+=1; print('MISMATCH', rn, rf, G.number_of_nodes(), G.is_directed())
# undirected: complete (eulerian iff odd n), cycle (eulerian), path (not), disconnected
for n in [3,4,5,10,50,101]:
    check(nx.complete_graph(n)); check(nx.cycle_graph(n)); check(nx.path_graph(n))
check(nx.disjoint_union(nx.cycle_graph(4), nx.cycle_graph(5)))  # disconnected eulerian-degrees
# directed: eulerian (balanced+strongly connected), unbalanced, not strongly connected
for n in [3,5,10,30]:
    check(nx.cycle_graph(n, create_using=nx.DiGraph))  # eulerian
    check(nx.DiGraph([(i,i+1) for i in range(n-1)]))   # path, not eulerian
# random directed
for seed in range(20):
    G=nx.gnp_random_graph(15+seed,0.2,seed=seed,directed=True); check(G)
    Gu=nx.gnp_random_graph(15+seed,0.25,seed=seed); check(Gu)
# self-loops (delegated path)
sl=nx.complete_graph(5); sl.add_edge(0,0); check(sl)
sld=nx.cycle_graph(5,create_using=nx.DiGraph); sld.add_edge(0,0); check(sld)
# empty/single
check(nx.Graph()); check(nx.DiGraph()); check(nx.Graph([(0,0)])); 
g1=nx.DiGraph(); g1.add_node(0); check(g1)
print('mismatches:',mism,'/',total)
def tm(f,r=9):
    ts=[]
    for _ in range(r): t0=time.perf_counter(); f(); ts.append(time.perf_counter()-t0)
    return min(ts)*1e3
for n in [101,301,601]:
    K=nx.complete_graph(n); gf=fnx.Graph(K)
    Kd=nx.cycle_graph(n,create_using=nx.DiGraph); gfd=fnx.DiGraph(Kd)
    print('K%d undir: nx=%.3f fnx=%.3f ratio=%.2f | dicycle dir: nx=%.3f fnx=%.3f ratio=%.2f'%(n, tm(lambda:nx.is_eulerian(K)), tm(lambda:fnx.is_eulerian(gf)), tm(lambda:fnx.is_eulerian(gf))/tm(lambda:nx.is_eulerian(K)), tm(lambda:nx.is_eulerian(Kd)), tm(lambda:fnx.is_eulerian(gfd)), tm(lambda:fnx.is_eulerian(gfd))/tm(lambda:nx.is_eulerian(Kd))))
