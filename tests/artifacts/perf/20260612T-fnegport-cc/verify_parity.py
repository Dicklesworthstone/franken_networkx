import warnings, time, random
warnings.filterwarnings('ignore')
import networkx as nx, franken_networkx as fnx
mism=0; nfound=0; nnone=0
for seed in range(60):
    G=nx.gnp_random_graph(12+seed%30,0.14,seed=seed,directed=True)
    rng=random.Random(seed)
    for u,v in G.edges(): G.edges[u,v]['weight']=rng.randint(-4,7)
    gf=fnx.DiGraph(G)
    src=0 if 0 in G else (list(G)[0] if len(G) else 0)
    if src not in G: continue
    try:
        rn=nx.find_negative_cycle(G,src,weight='weight'); ok_nx=True
    except nx.NetworkXError: rn=None; ok_nx=False
    try:
        rf=fnx.find_negative_cycle(gf,src,weight='weight'); ok_fx=True
    except nx.NetworkXError: rf=None; ok_fx=False
    if ok_nx!=ok_fx or (ok_nx and rn!=rf):
        mism+=1; print('MISMATCH seed',seed,'nx',rn,'fnx',rf)
    if ok_nx: nfound+=1
    else: nnone+=1
print('mismatches:',mism,'  (cycle-found:%d no-cycle:%d)'%(nfound,nnone))
def tm(f,r=7):
    ts=[]
    for _ in range(r): t0=time.perf_counter(); f(); ts.append(time.perf_counter()-t0)
    return min(ts)*1e3
from franken_networkx import _call_networkx_for_parity
rng=random.Random(1)
for nn in [120,250,400]:
    G=nx.gnp_random_graph(nn,0.06,seed=1,directed=True)
    for u,v in G.edges(): G.edges[u,v]['weight']=rng.randint(-1,9)
    gf=fnx.DiGraph(G)
    # ensure it has a cycle (else both error fast); measure regardless
    try:
        tnx=tm(lambda:nx.find_negative_cycle(G,0,weight='weight'))
        told=tm(lambda:_call_networkx_for_parity('find_negative_cycle',gf,0,weight='weight'))
        tnew=tm(lambda:fnx.find_negative_cycle(gf,0,weight='weight'))
        print('n=%d: nx=%.3f old=%.3f new=%.3f self-x=%.2f vs-nx=%.2f'%(nn,tnx,told,tnew,told/tnew,tnew/tnx))
    except Exception as e:
        print('n=%d skip (%s)'%(nn,type(e).__name__))
