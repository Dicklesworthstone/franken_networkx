import time,statistics,random,hashlib,json
import networkx as nx, franken_networkx as fnx

def build_pair(n,m,seed,directed=False,selfloops=False):
    rng=random.Random(seed)
    gn=(nx.DiGraph() if directed else nx.Graph()); gn.add_nodes_from(range(n)); edges=[]
    while gn.number_of_edges()<m:
        u=rng.randrange(n); v=rng.randrange(n)
        if u!=v and not gn.has_edge(u,v): edges.append((u,v)); gn.add_edge(u,v)
    if selfloops:
        for _ in range(max(1,n//30)):
            x=rng.randrange(n)
            if not gn.has_edge(x,x): edges.append((x,x)); gn.add_edge(x,x)
    gf=(fnx.DiGraph() if directed else fnx.Graph()); gf.add_nodes_from(range(n)); gf.add_edges_from(edges)
    return gn,gf

# broad parity: undirected(native), directed(py fallback), selfloops(py fallback), normalized=False(py fallback)
mism=0;checked=0
for seed in range(50):
    directed=(seed%5==0); sl=(seed%4==0)
    n=random.Random(seed).randrange(8,90); m=random.Random(seed+1).randrange(n,n*5)
    gn,gf=build_pair(n,m,seed,directed,sl)
    for node in list(gn.nodes())[:5]:
        for norm in (True,False):
            rn=nx.dispersion(gn,node,normalized=norm); rf=fnx.dispersion(gf,node,normalized=norm)
            checked+=1
            if rn!=rf: mism+=1; print(f"s{seed} dir{directed} sl{sl} node{node} norm{norm}: nx={rn} fnx={rf}")
    # alpha/b/c variants on undirected
    if not directed and not sl:
        rn=nx.dispersion(gn,list(gn.nodes())[0],alpha=2.0,b=1.5,c=0.5)
        rf=fnx.dispersion(gf,list(gf.nodes())[0],alpha=2.0,b=1.5,c=0.5)
        checked+=1
        if rn!=rf: mism+=1; print(f"s{seed} alpha/b/c mismatch")
print(f"PARITY: {checked} checks, {mism} mismatches")

# golden sha
gold_f={};gold_n={}
for seed in [1,2,7,42,99]:
    gn,gf=build_pair(150,900,seed)
    for node in [0,1,2]:
        gold_f[f"s{seed}n{node}"]=[[str(k),repr(v)] for k,v in fnx.dispersion(gf,node).items()]
        gold_n[f"s{seed}n{node}"]=[[str(k),repr(v)] for k,v in nx.dispersion(gn,node).items()]
shf=hashlib.sha256(json.dumps(gold_f,sort_keys=True).encode()).hexdigest()
shn=hashlib.sha256(json.dumps(gold_n,sort_keys=True).encode()).hexdigest()
print("GOLDEN MATCH:",shf==shn, shf[:16])

# realistic ego-network bench (clustered ego, real embeddedness)
def ego(mod,deg,seed=3):
    rng=random.Random(seed); G=mod.Graph(); G.add_nodes_from(range(deg*4+1))
    nb=list(range(1,deg+1))
    for x in nb: G.add_edge(0,x)
    for _ in range(deg*10):
        a=rng.choice(nb); b=rng.choice(nb)
        if a!=b: G.add_edge(a,b)
    return G
def bench(fn,reps=7):
    ts=[]
    for _ in range(reps):
        t=time.perf_counter(); fn(); ts.append(time.perf_counter()-t)
    return statistics.median(ts)
print("\nrealistic ego-network dispersion(G,0):")
for deg in [25,50,100,200]:
    Gn=ego(nx,deg); Gf=ego(fnx,deg)
    assert nx.dispersion(Gn,0)==fnx.dispersion(Gf,0)
    tn=bench(lambda:nx.dispersion(Gn,0)); tf=bench(lambda:fnx.dispersion(Gf,0))
    print(f"  deg={deg:3d}: nx={tn*1e3:8.3f}ms fnx={tf*1e3:7.3f}ms  speedup={tn/tf:6.1f}x")
