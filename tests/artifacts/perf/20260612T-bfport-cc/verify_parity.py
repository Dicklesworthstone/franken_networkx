import warnings, pickle, time, random
warnings.filterwarnings('ignore')
import networkx as nx, franken_networkx as fnx
golden=pickle.load(open('/tmp/bf_golden.pkl','rb'))
mism=0
for seed in range(14):
    directed=seed%2==0
    G=nx.gnp_random_graph(20+seed*5,0.08,seed=seed,directed=directed)
    rng=random.Random(seed)
    for u,v in G.edges(): G.edges[u,v]['weight']= rng.randint(-1,9) if seed%4==0 else rng.randint(1,9)
    gf=fnx.DiGraph(G) if directed else fnx.Graph(G)
    src=list(G.nodes())[0] if len(G) else 0
    try:
        pred,dist=fnx.bellman_ford_predecessor_and_distance(gf,src,weight='weight'); cur=(dict(pred),dict(dist))
    except Exception as e: cur=('EXC',type(e).__name__)
    if cur!=golden['s%d'%seed]: mism+=1; print('MISMATCH seed',seed)
print('mismatches vs golden(=nx):',mism,'/14')
# extra: direct vs nx on fresh tie-heavy + unweighted
extra=0
for seed in range(8):
    G=nx.gnp_random_graph(60,0.1,seed=seed+100,directed=seed%2==0); gf=fnx.DiGraph(G) if G.is_directed() else fnx.Graph(G)
    H=nx.DiGraph(G.edges()) if G.is_directed() else nx.Graph(G.edges()); H.add_nodes_from(G.nodes())
    fp,fd=fnx.bellman_ford_predecessor_and_distance(gf,0); np_,nd=nx.bellman_ford_predecessor_and_distance(H,0)
    if (dict(fp),dict(fd))!=(dict(np_),dict(nd)): extra+=1; print('EXTRA MISMATCH',seed)
print('unweighted/tie vs nx mismatches:',extra,'/8')
def tm(f,r=7):
    ts=[]
    for _ in range(r): t0=time.perf_counter(); f(); ts.append(time.perf_counter()-t0)
    return min(ts)*1e3
rng=random.Random(1)
for n in [200,300,500,800]:
    G=nx.gnp_random_graph(n,0.04,seed=1,directed=True)
    for u,v in G.edges(): G.edges[u,v]['weight']=rng.randint(1,9)
    gf=fnx.DiGraph(G)
    print('bench n=%d: nx=%.3f fnx=%.3f ratio=%.2f'%(n, tm(lambda:nx.bellman_ford_predecessor_and_distance(G,0,weight='weight')), tm(lambda:fnx.bellman_ford_predecessor_and_distance(gf,0,weight='weight')), tm(lambda:fnx.bellman_ford_predecessor_and_distance(gf,0,weight='weight'))/tm(lambda:nx.bellman_ford_predecessor_and_distance(G,0,weight='weight'))))
