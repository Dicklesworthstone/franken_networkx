import warnings, time
warnings.filterwarnings('ignore')
import networkx as nx, franken_networkx as fnx
from franken_networkx import _raw_is_eulerian
def tm(f,r=9):
    ts=[]
    for _ in range(r): t0=time.perf_counter(); f(); ts.append(time.perf_counter()-t0)
    return min(ts)*1e3
print('%-22s %8s %10s %10s %8s %7s'%('case','nx','old_raw','new','self-x','vs-nx'))
for n in [101,301,601]:
    K=nx.complete_graph(n); gf=fnx.Graph(K)
    tnx=tm(lambda:nx.is_eulerian(K)); told=tm(lambda:_raw_is_eulerian(gf)); tnew=tm(lambda:fnx.is_eulerian(gf))
    print('%-22s %8.3f %10.3f %10.3f %7.1fx %6.2fx'%('K%d undir'%n,tnx,told,tnew,told/tnew,tnew/tnx))
for n in [100,300,600]:
    Kd=nx.cycle_graph(n,create_using=nx.DiGraph); gfd=fnx.DiGraph(Kd)
    tnx=tm(lambda:nx.is_eulerian(Kd)); told=tm(lambda:_raw_is_eulerian(gfd)); tnew=tm(lambda:fnx.is_eulerian(gfd))
    print('%-22s %8.3f %10.3f %10.3f %7.1fx %6.2fx'%('dicycle%d dir'%n,tnx,told,tnew,told/tnew,tnew/tnx))
