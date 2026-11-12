import warnings, time
warnings.filterwarnings('ignore')
import networkx as nx, franken_networkx as fnx
from franken_networkx import _all_topological_sorts_inprocess, _call_networkx_for_parity
def dag(n,p,seed):
    g=nx.gnp_random_graph(n,p,seed=seed,directed=True); return nx.DiGraph((u,v) for u,v in g.edges() if u<v)
def tm(f,r=9):
    ts=[]
    for _ in range(r): t0=time.perf_counter(); f(); ts.append(time.perf_counter()-t0)
    return min(ts)*1e6
print('%-8s %12s %12s %12s %10s'%('n','nx(us)','old_deleg(us)','new_inproc(us)','self-speedup'))
for n in [250,600,1200,2000]:
    D=dag(n,0.05,1); gf=fnx.DiGraph(D)
    tnx=tm(lambda: next(nx.all_topological_sorts(D)))
    told=tm(lambda: next(iter(_call_networkx_for_parity('all_topological_sorts', gf))))
    tnew=tm(lambda: next(_all_topological_sorts_inprocess(gf)))
    print('%-8d %12.1f %12.1f %12.1f %9.1fx'%(n,tnx,told,tnew,told/tnew))
