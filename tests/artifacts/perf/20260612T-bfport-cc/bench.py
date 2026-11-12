import warnings, time, random
warnings.filterwarnings('ignore')
import networkx as nx, franken_networkx as fnx
from franken_networkx import _call_networkx_for_parity
def tm(f,r=7):
    ts=[]
    for _ in range(r): t0=time.perf_counter(); f(); ts.append(time.perf_counter()-t0)
    return min(ts)*1e3
rng=random.Random(1)
print('%-7s %8s %12s %10s %8s %7s'%('n','nx','old_deleg','new_port','self-x','vs-nx'))
for n in [200,300,500,800]:
    G=nx.gnp_random_graph(n,0.04,seed=1,directed=True)
    for u,v in G.edges(): G.edges[u,v]['weight']=rng.randint(1,9)
    gf=fnx.DiGraph(G)
    tnx=tm(lambda:nx.bellman_ford_predecessor_and_distance(G,0,weight='weight'))
    told=tm(lambda:_call_networkx_for_parity('bellman_ford_predecessor_and_distance',gf,0,weight='weight'))
    tnew=tm(lambda:fnx.bellman_ford_predecessor_and_distance(gf,0,weight='weight'))
    print('%-7d %8.3f %12.3f %10.3f %7.2fx %6.2fx'%(n,tnx,told,tnew,told/tnew,tnew/tnx))
