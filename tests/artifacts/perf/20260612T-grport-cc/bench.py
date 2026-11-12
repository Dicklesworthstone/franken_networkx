import warnings, time
warnings.filterwarnings('ignore')
import networkx as nx, franken_networkx as fnx
def old_naive(G, source, weight='weight'):
    dist={source:0}; pred={source:None}; n=G.number_of_nodes()
    for _ in range(n-1):
        updated=False
        for u,v,data in G.edges(data=True):
            if u not in dist: continue
            w=data.get(weight,1); nd=dist[u]+w
            if v not in dist or nd<dist[v]: dist[v]=nd; pred[v]=u; updated=True
        if not updated: break
    return pred,dist
def tm(f,r=7):
    ts=[]
    for _ in range(r): t0=time.perf_counter(); f(); ts.append(time.perf_counter()-t0)
    return min(ts)*1e3
print('%-7s %8s %10s %10s %8s %8s'%('n','nx','old_naive','new_port','self-x','vs-nx'))
for n in [200,300,500,800,1200]:
    G=nx.gnp_random_graph(n,0.04,seed=1,directed=True); gf=fnx.DiGraph(G)
    tnx=tm(lambda:nx.goldberg_radzik(G,0)); told=tm(lambda:old_naive(gf,0)); tnew=tm(lambda:fnx.goldberg_radzik(gf,0))
    print('%-7d %8.3f %10.3f %10.3f %7.2fx %7.2fx'%(n,tnx,told,tnew,told/tnew,tnew/tnx))
