import warnings, random
warnings.filterwarnings('ignore')
import networkx as nx, franken_networkx as fnx
mism=0; total=0; ntrue=0; nfalse=0
def transitive(n, perm):
    G=nx.DiGraph()
    for i in range(n):
        for j in range(i+1,n):
            G.add_edge(perm[i],perm[j])
    return G
for seed in range(20):
    n=8+seed
    rng=random.Random(seed); perm=list(range(n)); rng.shuffle(perm)
    G=transitive(n,perm); gf=fnx.DiGraph(G)
    for s in range(n):
        for t in range(n):
            rn=nx.tournament.is_reachable(G,s,t); rf=fnx.tournament.is_reachable(gf,s,t)
            total+=1
            if rn!=rf: mism+=1; print('MISMATCH',seed,s,t,'nx',rn,'fnx',rf)
            ntrue+=rn; nfalse+= not rn
# mixed: near-transitive with a few flipped edges
for seed in range(20):
    n=10+seed
    G=nx.tournament.random_tournament(n,seed=seed)
    # make it more hierarchical by removing strong connectivity: build from a partial order
    rng=random.Random(seed+99)
    H=nx.DiGraph()
    order=list(range(n)); rng.shuffle(order)
    for i in range(n):
        for j in range(i+1,n):
            a,b=order[i],order[j]
            if rng.random()<0.15: H.add_edge(b,a)  # occasional upset
            else: H.add_edge(a,b)
    gf=fnx.DiGraph(H)
    for s in range(0,n,2):
        for t in range(0,n,2):
            rn=nx.tournament.is_reachable(H,s,t); rf=fnx.tournament.is_reachable(gf,s,t)
            total+=1
            if rn!=rf: mism+=1; print('MIX MISMATCH',seed,s,t,'nx',rn,'fnx',rf)
            ntrue+=rn; nfalse+= not rn
print('mismatches:',mism,'/',total,' (true:%d false:%d)'%(ntrue,nfalse))
