import warnings, time
warnings.filterwarnings('ignore')
import networkx as nx, franken_networkx as fnx
mism=0; total=0
# score_sequence + is_tournament parity
for seed in range(25):
    n=5+seed
    G=nx.tournament.random_tournament(n,seed=seed); gf=fnx.DiGraph(G)
    if nx.tournament.score_sequence(G)!=fnx.tournament.score_sequence(gf): mism+=1; print('SS MISMATCH',seed)
    if nx.tournament.is_tournament(G)!=fnx.tournament.is_tournament(gf): mism+=1; print('IT MISMATCH(tourn)',seed)
    total+=2
# non-tournaments (is_tournament should be False)
ntf=0; ntt=0
for seed in range(25):
    n=6+seed
    G=nx.gnp_random_graph(n,0.3,seed=seed,directed=True); gf=fnx.DiGraph(G)
    rn=nx.tournament.is_tournament(G); rf=fnx.tournament.is_tournament(gf)
    if rn!=rf: mism+=1; print('IT MISMATCH(gnp)',seed,rn,rf)
    total+=1; ntt+=rn; ntf+= not rn
# self-loop case
sl=nx.DiGraph([(0,1),(1,2),(2,0),(0,0)])
print('selfloop is_tournament match:', nx.tournament.is_tournament(sl)==fnx.tournament.is_tournament(fnx.DiGraph(sl)))
# undirected error
try: fnx.tournament.score_sequence(fnx.Graph([(0,1)])); print('undir ss: NO RAISE')
except nx.NetworkXNotImplemented: print('undir ss: raised OK')
print('mismatches:',mism,'/',total,' (is_tournament gnp: %d True %d False)'%(ntt,ntf))
def tm(f,r=11):
    ts=[]
    for _ in range(r): t0=time.perf_counter(); f(); ts.append(time.perf_counter()-t0)
    return min(ts)*1e3
for n in [80,150]:
    G=nx.tournament.random_tournament(n,seed=1); gf=fnx.DiGraph(G)
    print('score_sequence n=%d: nx=%.4f fnx=%.4f ratio=%.2f'%(n, tm(lambda:nx.tournament.score_sequence(G)), tm(lambda:fnx.tournament.score_sequence(gf)), tm(lambda:fnx.tournament.score_sequence(gf))/tm(lambda:nx.tournament.score_sequence(G))))
    print('is_tournament  n=%d: nx=%.4f fnx=%.4f ratio=%.2f'%(n, tm(lambda:nx.tournament.is_tournament(G)), tm(lambda:fnx.tournament.is_tournament(gf)), tm(lambda:fnx.tournament.is_tournament(gf))/tm(lambda:nx.tournament.is_tournament(G))))
